# 河流篇：房间 / 角色 / 小游戏 / 剧本写法的约定（10-29，会话 A · 引擎）

给 B（小游戏 + 剧本）、C（外景美术）、D（室内 / 角色 / 音效）用。方案在 `docs/river_plan.md`，这里只写**格式和接口**。
引擎代码：`scripts/room_stage.gd`（房间）、`scripts/npc_generic.gd`（角色）、`scripts/closeup_ui.gd`（特写）、`story_runner.gd`（步骤）。

总规矩（和森林、驾驶舱一样）：
- **缺什么都不卡**：没有 room.json → 引擎按默认宽度画色块占位；没有图 → 色块；没有动作 → 退回 idle 打 `MISSING_ANIM <谁>.<名字>`；没有音效 → 静音。
  图放进来（`--headless --import` 以后）**不改代码就自动换掉占位**。没导入的新 png 引擎也会直接从文件读（只在编辑器 / 开发时管用）。
- 像素坐标一律**整数**、原生 480×270，不缩放。
- json 里写错的键引擎忽略并打一行 `ROOM_WARN` / `NPC_WARN`（每种一次），不崩。

---

## 1. 房间 `room.json`

### 1.1 放哪

| room id | 文件 | 谁画 |
|---|---|---|
| `river_bank` 河岸 | `art/river_city/river_bank/room.json` | C |
| `market` 高处市集 | `art/river_city/market/room.json` | C |
| `stairwell` 楼梯间（市集右头的门进去，石阶往下到旧街；10-31 加） | `art/river_city/stairwell/room.json`（`tools/river_stairwell_art.py`） | — |
| `oldstreet` 旧街 + 水闸 | `art/river_city/oldstreet/room.json` | C |
| `warehouse` 水下仓库 | `art/river_city/warehouse/room.json` | C |
| `southbridge` 南桥 + 货台 | `art/river_city/southbridge/room.json` | C |
| `river_home` 妮芙家（剖面小屋，在河岸里） | `art/river_home/room.json` | D |
| `cockpit` | 照旧 `art/cockpit/cockpit.json` | — |

引擎找房间：`art/river_city/<id>/room.json` → `art/<id>/room.json`。图的路径都相对 json 所在的文件夹。
剧本 `story_river.json` 的 `"rooms"` 列表里有的房间都认（`fade_to`、hotspot 的 `room`）。

### 1.2 坐标

- **房间坐标**：房间左上角 = (0, 0)，x 往右、y 往下，单位像素。房间高固定 270（一屏），宽 = `size[0]`。
- 房间放在世界里的 `origin`（世界坐标 = origin + 房间坐标）。不写就用默认（市集在河岸正上方、仓库在旧街正下方，竖直平移转场靠这个）：

| room | 默认 origin | 默认宽（占位用） |
|---|---|---|
| river_bank | (0, 0) | 1280 |
| market | (0, -270) | 1100 |
| stairwell | (2400, -270)（和市集一样高：往下 pan 到旧街靠这个） | 480 |
| oldstreet | (3000, 0) | 1200 |
| warehouse | (3000, 270) | 640 |
| southbridge | (6000, 0) | 1500 |
| river_home | 在河岸里（见 1.6） | 420 |

- 镜头：x 跟着晨、夹在 `[0, size[0]]` 里（房间比 480 窄就居中不动）；y 固定在房间中线（`origin.y + 135`），可用 `"cam_y"` 改（房间坐标）。

### 1.3 全部字段

```jsonc
{
  "size": [1280, 270],
  "origin": [0, 0],                     // 可选，见上表
  "env": "river_day",                   // river_day | underwater | "" —— 晨的光照预设；underwater 见第 5 节
  "bg": ["#1b2228", "#3a4752"],         // 可选：最底下的底色（上、下两色，横条渐变）；占位也用它

  "layers": [                           // 视差层，从后往前写
    {"id": "sky",  "img": "sky.png",  "scroll": 0.0, "y": 0,   "tile": true},
    {"id": "far",  "img": "far.png",  "scroll": 0.25, "y": 40, "tile": true},
    {"id": "main", "img": "main.png", "scroll": 1.0, "y": 0},
    {"id": "water","img": "water.png","scroll": 1.0, "y": 196, "water": true, "shader": "water", "alpha": 0.8},
    {"id": "front","img": "front.png","scroll": 1.25,"y": 200, "front": true}
  ],

  "ground": 228,                        // 晨脚底踩的那一行（房间 y）；或折线 [[0,228],[300,228],[340,236],[1280,236]]
  "walk": [16, 1264],                   // 晨能走的左右范围（房间 x）
  "walk_when": [                        // 可选：条件范围，从上往下第一个满足的生效，都不满足用 walk
    {"prop": "oldstreet_steps=submerged", "walk": [16, 600]},
    {"not": ["river_sluice_done"], "walk": [16, 600]}
  ],

  "markers": {"river_bank_steps": 310, "river_bank_post": 420},   // 房间 x；也可以 {"x": 310}
  "objects": { ... 见 1.4 ... },
  "water":   { ... 见 1.5 ... },
  "portals": [ ... 见 1.7 ... ],
  "ambient": [ ... 见 1.8 ... ],
  "walkers": [ ... 见 1.9 ... ],
  "residents": [{"who": "jellyfish", "at": "stairwell_jelly", "z": -2, "face": 1}],   // 见 1.9.1
  "scripts": [ ... 见 1.10 ... ],
  "rope":    { ... 见 5 ... }
}
```

**layers**
- `img`：图（相对 json）。缺图：按层名画占位色块。
- `scroll`：横向视差。1 = 跟地面一起动（主层）；0 = 钉在屏幕上；0.25 = 远景；>1 = 前景。
  层的屏幕 x = `x − 镜头左边缘(房间 x) × scroll`（x 默认 0）。**不 tile 的层宽至少要 `480 + (房间宽 − 480) × scroll`**，不然卷到头露边。
- `tile`：横向无缝循环（图宽随意，接缝要看不出）。
- `y`：图上沿的房间 y。**竖直方向没有视差**（竖直平移时所有层一起动，楼上楼下才对得上）。
- `z`：前后顺序，人物是 0。不写：按写的顺序 −100、−99…（都在人后面）；`"front": true` = 在人前面（z 100+）。
- `shader`：`"water"`（`river_water.gdshader`）、`"wet"`（`city_wet.gdshader`）、`"sway"`（水草摆动，`underwater_*` 那套）、不写 = 不用。`"shader_params": {…}` 原样传给 `set_shader_parameter`。
- `alpha`（默认 1）、`drift`（每秒自己横向漂几像素，云 / 水面用，可负）。
- `water: true`：这层跟着水位上下动（见 1.5）。

**ground**：一个数 = 平地；折线 = 每列线性插值后取整。NPC 也踩这条线。

### 1.4 objects（物件 / 道具，剧本 `prop` 换状态）

和驾驶舱 `cockpit.json` 一个写法：

```jsonc
"objects": {
  "river_bank_plane": {"x": 120, "y": 150, "w": 140, "h": 70, "frames": 3,
                       "states": {"beached": 0, "straps_drying": 1, "fixed": 2}},
  "sluice_pipes":     {"x": 610, "y": 120, "w": 40, "h": 30, "frames": 6,
                       "states": {"bubble_3": [0, 1], "bubble_2": [2, 3], "bubble_1": [4, 5], "still": 0}, "fps": 5},
  "river_bank_crates":{"x": 300, "y": 190, "w": 50, "h": 38, "frames": 3, "states": {"tail": [0, 1], "tail_still": 2},
                       "ms": 200},
  "postman_rail":     {"x": 700, "y": 40, "w": 60, "h": 10, "on": "river_bank_plane=fixed", "front": true},
  "oldstreet_bell":   {"x": 900, "y": 200, "w": 8, "h": 10, "default": "hidden"},
  "warehouse_float":  {"x": 200, "y": 180, "w": 16, "h": 14, "click": [196, 176, 24, 22]}
}
```

- `x, y` = 图左上角（房间坐标）；`w` = 一帧的宽，`h` 高；`frames` 横排帧数。图 = `<id>.png`（`"img"` 可改）。
- `states`：`{"状态": 第几帧}` 或 `{"状态": [起, 止]}`（循环播）；也可写成 `["a", "b"]`（第 0、1 帧）。
  没有 states 时找 `<id>_<状态>.png`。都没有 → 第 0 帧 + `ROOM_WARN`。`hidden` / `gone` / `taken` = 藏起来，`shown` / `default` = 默认。
- 帧速：`fps`（默认 10 = 100ms 一帧，agent 画的一律这样）或 `ms`（美术组 / 画师给的，保留原帧时长）。
- `z`（默认 −1，在人后面；`"front": true` = 人前面）、`on`（只在某物件是某状态时显示）、`default`（剧本还没 prop 过时的状态）。
- `click`：点击框 `[x, y, w, h]`（默认 = 图的矩形）。hotspot 的 `at` 写物件 id 时用它。
- 剧本里 `prop` 了、但 objects 里没有的 id：**还没有 room.json 的房间**，引擎在同名 marker 那里画一块占位色块（每个状态换一档深浅）；
  **已经有 room.json 的房间不画**（10-30：成片里会是一块灰方块，作者截图里出现过），只打一行
  `ROOM_WARN <房间>: 剧本 prop 了 <id>，room.json 的 objects 里没有`——画一个真物件，或者纯剧情状态就加一个 1×1 的空物件。
  water.prop（水位）、rope.prop（导绳开关）也算房间自己的，不会被当成缺物件。

### 1.5 water（水位）

```jsonc
"water": {"y": 196,                     // 平时的水面（房间 y）——water:true 的层按这个 y 画
          "prop": "oldstreet_steps",    // 这个 prop 的状态 = 水位
          "levels": {"submerged": 196, "l1": 206, "l2": 216, "l3": 226, "revealed": 240},
          "sec": 1.5}                   // 换水位用多久（smoothstep 缓起缓停）
```

- 水位变了：所有 `water: true` 的层整体往下 / 往上挪（挪的量 = 新水位 − `y`），整像素。
- 剧本 `{"do": "prop", "id": "oldstreet_steps", "state": "l2"}` 或 `{"do": "water", "room": "oldstreet", "y": 216}`（见第 4 节）。
- 小游戏代码：`stage.set_water(216, 1.5)`、`stage.water_y()`（第 3.4 节）。
- 水面线以下的人：不额外处理（水层是半透明的、在人前面就盖住腿；在人后面就不盖）。要「泡在水里」就把水层设 `front: true`。

### 1.6 剖面小屋（river_home，学树屋）

`art/river_home/room.json`：

```jsonc
{
  "kind": "house",
  "host": "river_bank",                 // 在哪个房间里
  "x": 640,                             // 图的底边中点放在 host 的哪个 x（踩在 host 的地面上）
  "size": [420, 200],
  "back": "back.png",                   // 屋内 + 外墙（一直显示，在人后面）
  "front": "front.png",                 // 前墙（进屋 0.5 秒淡出、出屋淡回来；在人前面）
  "light": "light.png",                 // 可选：屋里的光（半透明，在人后面、物件前面）
  "view": "view.png",                   // 可选：窗玻璃遮罩（同样大小，玻璃 = 不透明）。back 在玻璃处要透明；引擎透过去画 host 里
                                        //   比 main 远的层（scroll < 1、不是 front）+ 头顶补的夜空，位置每帧照抄 → 跟着视差动（10-31 妮芙家大窗）
  "floor": 190,                         // 屋内地板那一行（图里的 y）
  "walk": [30, 390],                    // 屋里能走的范围（图里的 x）
  "door": 40,                           // 门（图里的 x）：在门口互动进出，不跳位置
  "markers": {"river_home_table": 200, "river_home_window": 330},   // 图里的 x
  "objects": { ... 和 1.4 一样，x / y 是图里的左上角 ... }
}
```

- **小屋里所有坐标都是「图里的像素」**（左上角 = 0,0）。引擎换算到世界。
- 进出屋 = 剧本 `fade_to river_home` / 从屋里 `fade_to river_bank`：前墙淡出 / 淡入，不黑屏，镜头往屋子中心收（树屋同款）。
- 屋外的人站在前墙的横向范围里时，晨进屋时一起淡掉（树屋同款）。

### 1.7 portals（房间之间怎么走）

```jsonc
"portals": [
  {"edge": "left",  "to": "market", "at": "market_back",   "kind": "walk_fade"},
  {"edge": "right", "to": "southbridge", "at": "southbridge_entry", "kind": "walk_fade", "need": ["river_south_open"]},
  {"to": "market", "at": "market_entry", "kind": "pan_up", "x": 1220}        // 不在两头：只给 fade_to 用（见下）
]
```

- `edge`：晨走到这头的墙、**顶着走 0.35 秒**就过去（推广森林的 `portal_to`）。`need` / `not` 不满足 = 就是墙。
- 有 `x`、没有 `edge` 的：不会自己触发（楼梯口这种在中间的，由 hotspot 的 scene 里 `fade_to` 去）。
- `kind`（转场做法）：
  - `fade`：黑屏淡出淡入（默认）。
  - `walk_fade`：边走边黑，淡入时晨从画面外走进来（`fade_to` 的 `leave` + `cam`）。
  - `pan_up` / `pan_down`：渐黑再渐亮，但看得出在往上 / 往下走（10-31 作者定；不拼两个房间、不要接缝带、不要夜空）：
    人淡掉 → 渐黑 0.85 秒的同时镜头在这个房间里往上（下）移 40 像素、平滑起步 → 黑着换房间 →
    渐亮 0.85 秒的同时镜头从新房间下（上）面 40 像素接着移、减速停住 → 人淡出来（`story_runner._pan_to`，`PAN_SHIFT` / `PAN_HALF`）。
    镜头移出房间露出来的地方由 `level_forest.gd` 的房间上下盖黑盖住；显示中的房间上下以外一律盖黑，窗口比例怎么变都看不到别的房间。
  - `door`：小屋前墙淡出 / 淡入（river_home 自动用这个）。
- **剧本里的 `fade_to` 也查这张表**：从 A 房间 `fade_to` B 房间时，A 的 portals 里有去 B 的就用它的 `kind`（剧本步骤里写了 `"kind"` 以剧本为准）。

### 1.8 ambient（环境声）

```jsonc
"ambient": [
  {"name": "river_flow", "db": -10},                   // 不写 x：整个房间同样大
  {"name": "pipe_gurgle", "x": 610, "db": -6, "range": 260}   // 写 x：随晨的距离变小、左右声道随方位
]
```
文件 `audio/sfx/<name>.ogg`（`.wav` 也认）。进房间淡入、出房间淡出。剧本的 `ambient` 步骤照旧能用。

### 1.9 walkers（背景里走过的小人：邮差、卖菜的人、兜帽路人）

```jsonc
"walkers": [
  {"npc": "postman", "path": [[700, 44], [980, 44]], "speed": 18, "pause": [3, 8], "z": -20, "loop": "pingpong"},
  {"npc": "hood_a",  "path": [[0, 120], [1280, 120]], "speed": 12, "z": -40, "loop": "wrap", "count": 3}
]
```
- `npc` = `art/characters/<npc>/<npc>.json`（第 2 节）；走路播 `walk`、停下播 `idle`。不能点。
- `path` 的 y = 脚底那一行（房间坐标）。`loop`：`pingpong`（来回）/ `wrap`（走出去从另一头再进来）/ `once`。
- `pause`：到头停几秒（数或 `[最少, 最多]`）。`count`：同时几个（错开出发）。

### 1.9.1 residents（住在这个房间里的人，10-31）

```jsonc
"residents": [{"who": "jellyfish", "at": "stairwell_jelly", "z": -2, "face": 1}]
```
- 和 walkers 不一样：是剧本里的角色（`art/characters/<who>/<who>.json`，`say` / hotspot 都认），一直待在 `at` 那里。
- 晨进这个房间时她还不在这儿就放好、显示出来（`story_runner._place_residents`，在 `_teleport` 里）——不用剧本 `show`，
  跳节拍、F8 传送、自由探索进来都一样在；晨不在这个房间时照常藏着。`z` = 前后（−2 = 压到物件 / z −1 的层后面，柜台后面的人）；`face` = 朝向。

### 1.10 scripts（房间自己的装饰脚本）

```jsonc
"scripts": [{"script": "res://scripts/city_pigeons.gd", "x": 0, "y": 0, "z": -60, "params": {"count": 6}}]
```
引擎 `new()` 一个，作为房间的子节点放在 (x, y)（房间坐标），`params` 逐个 `set()` 上去，再 `add_child`。
C 想加鸽子、闪烁窗灯、光点、小鱼之类自己的效果用这个，不用改引擎。脚本里拿房间：`get_parent()`（room_stage）。

### 1.11 占位（没有 room.json 时）

引擎画：底色 `bg`（河流身份色灰蓝）+ 一条地面 + 一条半透明水带 + 房间名；markers 没给坐标的，按剧本里第一次出现的顺序在房间里排开；
`prop` 过的东西在 marker 那里画色块。剧本照样能从头走到尾。

---

## 2. 角色 `art/characters/<id>/<id>.json`

`<id>` = 剧本 `say` / `show` / `walk` 里的名字（`niff`、`ting`、`keeper`），背景小人随便起（`postman`、`vendor`、`hood_a`）。
鹿（`deer`）、弥洛（`miluo`）照旧用原来的脚本，不读这个。

```jsonc
{
  "frame": [24, 40],                    // 一帧宽高
  "sheet": "ting.png",                  // 默认用哪张图（相对 json；横排，多行也行：帧号 = 行 × 每行帧数 + 列）
  "anchor": [12, 39],                   // 脚底点在帧里的像素（站在地面那一行上）
  "faces": "right",                     // 图里朝哪边画的："right"（= 1）/ "left"；另一边引擎水平翻转
  "ms": 100,                            // 默认帧时长（agent 画的 100；美术组的照原样，比如鲸鱼妹 200）
  "tint": true,                         // true = 跟晨一样吃环境光（比晨暗一档）；false = 原色不改（美术组的图）
  "head": 38,                           // 对话框锚点：脚底往上多少像素
  "speed": 36,                          // walk 的速度（像素 / 秒）
  "color": "#8a7a68",                   // 没图时占位色块的颜色
  "anims": {
    "idle":  {"frames": [0, 1, 2, 1], "ms": 200},
    "walk":  {"frames": [3, 4, 5, 6, 7, 8]},
    "talk":  {"frames": [9, 10]},       // 说话时自动播（没有就用 idle）
    "nod":   {"frames": [11, 12, 11], "loop": false},
    "hand_coat": {"sheet": "ting_coat.png", "frames": [0, 1, 2, 3], "loop": false, "hold": true}
  },
  "alias": {"hand_bag": "hand_coat", "hand_board": "hand_coat", "count": "nod"},
  "forms": { ... 见下 ... }
}
```

- `anims` 每个动作：`frames`（帧号）、`ms`（覆盖默认）、`sheet`（覆盖默认图）、`loop`（`idle` / `walk` / `talk` / `swim` 默认循环，其余默认播一遍）、
  `hold`（播完停在最后一帧，直到下一个动作 / 走路；不写 = 播完回 idle）、`anchor`（这个动作的帧尺寸不一样时）、`frame`（同上）。
- 找动作的顺序：`anims[名字]` → `alias[名字]` → 引擎通用别名（`look_*` → idle、`hand_*` / `give*` → `give`、`point*` → `point`…）→ `idle` + 打 `MISSING_ANIM <id>.<名字>`。
- 脚下有一块硬边小阴影（引擎画）。
- **没有 json 或没有图**：画 `color` 的竖条色块 + 名字，所有动作打 `MISSING_ANIM`，剧情照常播。

### 2.1 多套形态 `forms`（妮芙：岸上 / 水下）

```jsonc
{
  "tint": false,
  "head": 40,
  "forms": {
    "swim": {"sheet": "niff_swim.png", "frame": [71, 46], "anchor": [35, 40], "faces": "right",
             "anims": {"swim": {"frames": [0, 1, 2, 3], "ms": 200}}},
    "land": {}
  },
  "form": "land"                        // 一开始用哪套
}
```
- 每套形态里可以写顶层的任何键（`frame` / `sheet` / `anchor` / `faces` / `ms` / `anims` / `alias` / `speed`…），没写的继承顶层。
- 形态里空的（`"land": {}`，等美术组）= 占位色块。
- 换形态：房间 `env: underwater` 时自动用 `swim`、出来自动回 `land`；剧本 `{"do": "form", "who": "niff", "form": "swim"}` 手动换（在黑场 / 镜头穿过水面那一下换）。
- `swim` 形态里：`idle` / `walk` 没有就都用 `swim`；引擎让整只上下 1 像素慢浮（不改图）。

### 2.2 谁做哪个

| id | 谁 | 备注 |
|---|---|---|
| `niff` | D 导入（`tools/niff_from_gif.py`），只写 `swim`，`land` 留空 | 美术组岸上图来了照同样方法补进 `land` |
| `ting` | D 画 | 100ms；动作名照剧本：`check` `coat_on_chair` `count` `hand_bag` `hand_board` `hand_coat` `hold_shell` `look_down` `nod` `open_shell` `show_record` |
| `keeper` | D 画 | 柜台后 |
| `postman`、`vendor`… | D 画 | 只要 `idle` + `walk`，给 walkers 用 |

剧本里用到的全部动作名：`--story_check` 会列出 `STORY_CHECK info: MISSING_ANIM niff.xxx`（谁缺哪个一目了然）。

---

## 3. 小游戏接口 `{"do": "mechanic"}`

### 3.1 剧本里

```json
{"do": "mechanic", "id": "river_sluice"}
{"do": "mechanic", "id": "river_salvage", "items": ["pipe_joint", "tea_tin"], "key": "pipe_joint"}
```
- 引擎加载 `res://scripts/<id>.gd`（文件不存在 → 打一行警告、当它玩完了，接着播下一步；`--story_check` 报 error）。
- 步骤里除了 `do` / `id`，别的键随便加，原样传给脚本（`step`）。
- 小游戏玩完 = `run()` 返回，剧本接着播下一步。小游戏里要分支就自己设 flag，剧本下一步用 `if`。
- **`"sets": ["river_sluice_done", …]`（建议写）**：脚本里会设的 flag。`--story_check` 靠它知道这些 flag 有地方设，
  F8 / `--beat` 跳节拍靠它知道「要跳到这个 flag 得经过这个小游戏」。不写也能跑，只是 check 会报「没有地方设」。
- 引擎在 `run` / `auto` / `ff` 返回后自动在进度里记 `_done: true`（自动玩据此判断这一步还算不算「有进展」）。脚本编译不过时引擎当它玩完了（打警告），剧本不会卡。

### 3.2 脚本要有的函数

```gdscript
extends RefCounted
## river_sluice：水闸调节（原文 105–107）……玩法写在文件头

## 正常玩：等玩家玩完再返回（await）。要做的：设 flag / give / 存进度 / 最后打 MECH <id> done。
func run(level: Node2D, world: Node2D, story: Node, step: Dictionary) -> void:
	...

## --story_auto（自动玩）时代替 run：自己把题解了（可以走过去、转闸轮，演一遍正确解法），结果和 run 玩通一样。
func auto(level: Node2D, world: Node2D, story: Node, step: Dictionary) -> void:
	...

## 跳节拍（--beat、F8「节拍」）时调：**同步**、不 await、不演，直接把结束后的 flag / prop / 物品 / 进度设好。
func ff(story: Node, step: Dictionary) -> void:
	...

## --story_check 时调（可选）：返回错误文字列表（比如要的 marker / 物件 / 物品剧本里没有）。
func check(story: Node, step: Dictionary) -> Array:
	return []
```
- 引擎每次 `new()` 一个新实例，`run` 完就丢掉；**状态别放成员变量过夜**，放进度（3.3）。
- 结束时打印 `print("MECH %s done" % id)`（引擎在 `run` / `auto` 返回后也会补打一行 `MECH <id> returned`）。
- 不许让玩家失败、不许计时（作者定）。错的操作只回退。

### 3.3 进度（「已完成的小游戏进度保留」，原文 102）

```gdscript
var p: Dictionary = story.mech_load("river_sluice")     # 没存过 = {}
p["wheel_1"] = 3
story.mech_save("river_sluice", p)                      # 存进 StoryState（跟着存档、换章、F8 跳节拍走）
```
- 存在 `StoryState.props["mech.<id>"]`（JSON 字符串）。只放能 JSON 的东西（数、字符串、数组、字典）。
- 离开房间再回来、F8 跳节拍都还在。`run()` 开头先 `mech_load`，从上次停的地方继续。

### 3.4 脚本能用的东西（引擎保证有）

**story（story_runner.gd）**
| 用法 | 做什么 |
|---|---|
| `await story.run_steps([...])` | 播一串剧本步骤（`say` / `walk` / `anim` / `prop` / `sfx` / `give`… 全部能用），播完返回。小游戏里的台词就这么播。 |
| `var r: Dictionary = await story.wait_interact(spots)` | 临时加几个可互动的点，等玩家互动其中一个（和普通 hotspot 一样：靠近按键 / 鼠标点 / 用背包里的东西）。返回 `{"id": 点的 id, "item": 用的物品 id 或 ""}`。返回后这些点自动撤掉。 |
| `var z: String = await story.closeup(spec)` | 开特写面板（第 6 节），返回点到的区域 id（关掉 = ""）。 |
| `story.npc("niff")` | 角色节点（晨 = `"chen"`）。 |
| `story.mech_load(id)` / `story.mech_save(id, d)` | 进度（3.3）。 |
| `story.auto` | `""` / `"main"` / `"full"`（在不在自动玩）。`story.ff`：在不在跳节拍。 |
| `story.room_of_marker(name)` | marker 在哪个房间。 |

`wait_interact` 等的时候剧情是「放手」的（晨能自由走、背包能开、跟随的人照常跟），只有这些临时点能互动，房间两头的入口不通；
返回以后又回到过场状态。`story_end` 会放开镜头，要镜头停住的在返回后再 `camera_hold_at`。

`spots` 每一项：`{"id": "wheel_1", "at": "sluice_wheel_1" 或物件 id 或世界 x, "label": {"zh": "闸轮", "en": "Wheel"}, "accepts": ["float_box"]（可选）, "range": 20（可选）}`。
`at` 写物件 id 时点击框 = 物件的 `click` / 图的矩形，物件挪了点也跟着挪（「会动的 hotspot」）。

**world（story_world.gd）**
| 用法 | 做什么 |
|---|---|
| `world.stage("oldstreet")` | 那个房间（room_stage.gd）；`world.cur_stage()` = 晨现在在的 |
| `world.room` | 晨现在在哪个房间（字符串） |
| `world.set_prop(id, state)` / `world.prop_state(id)` | 物件换状态（存进 StoryState） |

**stage（room_stage.gd，一个房间）**
| 用法 | 做什么 |
|---|---|
| `stage.mx(name)` → float | marker 的**世界** x |
| `stage.to_world(Vector2)` / `stage.to_local_px(Vector2)` | 房间坐标 ↔ 世界坐标 |
| `stage.ground_y(world_x)` | 那一列的地面（世界 y） |
| `stage.object(id)` → Sprite2D | 物件节点（可能是占位） |
| `stage.move_object(id, room_pos: Vector2, sec)` | 物件平滑挪到房间坐标（smoothstep，取整）；`await` 它等挪完 |
| `stage.set_water(y, sec := 1.5)` / `stage.water_y()` | 水位（房间 y） |
| `stage.add_node(node, z := 0)` | 往房间里加自己的节点（房间坐标，z 同 layers） |
| `stage.set_walk(Vector2(左, 右))` / `stage.clear_walk()` | 临时改晨能走的范围（房间 x；导绳到头这种） |

**level（level_forest.gd）**：`level.chen`、`await level.fade_to_black(sec)` / `level.fade_from_black(sec)`、`level.camera_hold_at(世界坐标)` / `level.camera_release()`。

### 3.5 六个小游戏的 id（B 写）

`river_salvage`、`river_explore_order`、`river_sluice`、`river_warehouse`、`river_bridge_view`、`river_dock_plates`（最后一个也可以纯剧本数据写，不用 .gd）。
`story_river.json` 里 6 个 `todo_mechanic` 换成 `{"do": "mechanic", "id": …}`。`todo_mechanic` 引擎也认（当成空步骤跳过，`--story_check` 报 info），换完前剧本照样能走通。

---

## 4. 剧本新写法（`story_river.json`）

| 写法 | 意思 |
|---|---|
| `{"do": "mechanic", "id": "river_sluice", …}` | 小游戏（第 3 节） |
| `{"do": "form", "who": "niff", "form": "swim"}` | 换形态（2.1） |
| `{"do": "follow", "who": "niff", "on": true, "gap": 34}` | 自由走动时她跟在晨身后（`gap` 默认 34，弹簧追目标，停下转向晨，帧速不变）。`on: false` 不跟了。 |
| `fade_to` 带 `"with": ["niff"]` | 同行的人一起过去，**并且自动 `follow on`**（到了以后她跟着晨）。想到了以后不跟，后面接一步 `follow on: false`。 |
| `fade_to` 带 `"kind": "pan_up"` | 指定转场（不写就查 portals 表，见 1.7） |
| `{"do": "water", "room": "oldstreet", "y": 216, "sec": 1.5}` | 水位直接设到某个 y（房间坐标）。也可以 `{"do": "prop", "id": "oldstreet_steps", "state": "l2"}`（按 room.json 的 levels）。`"wait": false` 不等水停。 |
| `{"do": "closeup", …}` | 特写面板（第 6 节） |
| `{"do": "prop", …}` | 照旧；房间物件、小屋物件、驾驶舱物件都认（按 id 找在哪个房间） |
| `{"do": "show", "who": "ting", "at": "river_bank_post"}` | 照旧；`at` 在哪个房间人就在哪个房间（不在晨的房间就看不见） |
| `{"do": "anim", "who": "niff", "name": "wave"}` | 照旧；NPC 按第 2 节找动作 |
| `{"do": "camera", …}` | 照旧；y 自动用当前房间的中线 |

**markers 写 0** = 用 room.json 里的坐标（C / D 定）；写非 0 = 房间坐标（覆盖美术的）。和驾驶舱一样。
marker 在哪个房间：room.json 的 markers 里有就是那个房间 → 名字以 `<room>_` 开头的 → hotspot / fade_to 引用它时写的房间。
**所以 C / D 在 room.json 的 `markers` 里把剧本的 marker 名字写全**（特别是不带房间前缀的 `sluice_wheel_1/2/3`、`sluice_pipes`）。

hotspot 的 `room` 写房间 id；`at` 可以是 marker、物件 id（跟着物件走）、NPC 名（`niff`：跟着她走）。

---

## 5. 水下（`env: underwater`）

- 晨移动 ×0.55（只改速度，动画照旧 100ms 一帧）；面罩处冒气泡（`underwater_bubbles.gd`）；焦散 + 光柱（room.json 的 layers / scripts 自己加）；
  所有音效加一点低通；妮芙自动 `swim` 形态。
- 晨戴面罩的动作奥斯卡画：`chen.gd` 里有 `uw_idle` / `uw_walk` / `uw_reach` 就用，没有就用平常的并打 `MISSING_ANIM uw_idle`……
- 导绳：

```jsonc
"rope": {"prop": "warehouse_rope", "on": "on",       // 这个 prop 是这个状态时导绳连着晨
         "anchor": [40, 150],                        // 绳头系在哪（房间坐标）
         "end": 600,                                 // 走到这个 x 晨就停（看得见的边）
         "color": "#9aa6a0", "knots": [160, 300, 450]}   // 绳结的 x（画成小疙瘩）
```
  引擎画一条从 `anchor` 到晨腰间的线（下垂一点、整像素）。

---

## 6. 特写面板（closeup_ui.gd）

全屏一张图（本子页、来客册、图纸、设备柜、装卸记录、照片、防水板……），可带可点的区域。点空白 / 按 Esc / E / 空格关掉。

### 6.1 图放哪（D 画）

`art/river_story/closeup_<名字>.png`，原生，最大 480×270（小于一屏就居中，四周压暗）。
同一样东西几个状态 / 页：`closeup_<名字>_<状态>.png`（比如 `closeup_niff_notebook_page1.png`、`closeup_board_l2.png`）。

### 6.2 剧本写法

```jsonc
{"do": "closeup", "img": "niff_notebook_page1"}                         // 看一眼，关掉接着播
{"do": "closeup", "img": "niff_notebook", "state": "page1"}            // 同上（= closeup_niff_notebook_page1.png）
{"do": "closeup", "img": "warehouse_cabinet",
 "zones": [{"id": "d1", "rect": [60, 80, 50, 30], "label": {"zh": "「接头」", "en": "\"Joints\""}, "scene": "cab_wrong"},
           {"id": "d4", "rect": [180, 80, 50, 30], "label": {"zh": "「读取头」", "en": "\"Reading heads\""}, "scene": "cab_right"}],
 "close": false}                                                        // 有 zones：点一个就跳到它的 scene（像 pick）；close:false = 必须点一个
{"do": "closeup", "img": "board", "lines": [{"zh": "第一道：二格", "en": "1st: 2"}], "added": true}   // 图上叠手写行（防水板）
```
- `rect` 是**图里的像素**。没写 `scene` 的 zone：点了只是关掉，返回 id（小游戏代码里用）。
- `lines`：叠在图上的手写字（`"at": [x, y]` 第一行的位置，默认图左上 + 16），一行一个；防水板记刻度用。
- 鼠标停在 zone 上：轻轻亮一档 + 显示 label；键盘 ← → 在 zones 之间切、E / 空格选。
- **缺图**：画一块纸色的面板，上面写名字和状态，zones 画成框 + label，照样能点。
- hotspot 也能直接开特写：`{"id": "plan", "at": "oldstreet_marks", "label": …, "closeup": "ting_plan"}`（不用写 scene）。
- 自动玩：有 `scene` 的 zones 按 pick 的规矩选（选能推进的）；没 zones 的停 0.3 秒关掉。

---

## 7. 换章 / 测试（B 用来验）

- `-- --chapter=river --story_check`：0 error。新增 info：`MISSING_ANIM niff.xxx`、缺的音效、`mechanic 脚本还没有`。
- `-- --chapter=river --story_auto`（`=full`）：一路到驾驶舱「未完待续」，打 `STORY_DONE`；小游戏走 `auto()`。
- `-- --chapter=river --story_fuzz=120 --seed=n`、`--dev_test`、`--beat=<flag>`。
- `-- --story_auto --story_chain`：森林 → 飞行一 → 河流连着走。
- F8：「传送」按房间分组；「节拍」能跳到河流篇的任意 flag（小游戏走 `ff()`）。
- 输出：`MECH <id> done`、`ROOM <id> enter`、`CHAPTER flight1 → river`、`MISSING_ANIM <谁>.<名字>`、`ROOM_WARN …`、`NPC_WARN …`。

- `-- --room_placeholder`：不读任何 room.json，全用占位（验引擎和剧本本身，不受美术进度影响；chain 测试也能加）。
- 直接进河流篇的起点：飞行一自动玩完（烧了蓝色石头）；`-- --river_seed=card` 或 F8「节拍」页切成烧了通勤卡那版（原文 119）。

## 8. 引擎已经做了的转场 / 演出（会话 A，10-29）

- 河流篇开场：黑场 0.6 秒以内，镜头从水面往上 60 像素缓缓抬到岸上（接飞行一「卡进狭窄的水道」）。
- 下水 / 上水（进出 `env: underwater` 的房间，10-30 作者：「切换很不好，实在不行逐渐黑再逐渐亮吧」）：正弦缓入缓出渐黑 0.8 秒，开头放一声 `splash_in` / `splash`（剧本刚放过的不叠），黑着换房间、镜头直接到位，停 0.2 秒，再渐亮 0.8 秒。原来那块漫过人的半透明水和亮纹删了。
- 河岸 → 驾驶舱（`depart` 的 `fade_to cockpit`）：房间物件 `river_bank_plane` 预热（船底泛光、1 像素抖）→ 反重力竖直升 40 像素（ship_glow.gd 泛光）
  → 往左上加速飞出画面 → 淡到黑。没有这个物件就直接淡出。剧本步骤一步没动。
- 水下：晨移动 ×0.55（只改速度）、嘴边冒泡（underwater_bubbles.gd）、SFX 总线加低通；妮芙自动换 swim。
- 镜头平时往晨面朝的方向多看 36 像素（森林同款）；房间 room.json 有 `viewfinder` 时，小游戏（mechanic）进行期间镜头正对晨（不多看），
  所以南桥取景框按「晨站在 chen_x、镜头左边缘 = cam_x = chen_x − 240」出图就对得上（房间两头被夹住的地方除外）。
- 自动玩（`--story_auto`）在多房间章节会按房间找路（哪个房间还有能推进剧情的点，就沿着出口一路走过去）。

改了这份约定会在共享笔记里留一行（`river-engine.md`）。
