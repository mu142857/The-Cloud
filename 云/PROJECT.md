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
