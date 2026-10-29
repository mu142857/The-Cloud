# 《云》英文版翻译约定（10-29）

作者要一个英文版。中文是权威：**中文一个字都不许改**，只填 `"en"`。三个翻译 agent 同时做，分工见最后。

## 写在哪
- 剧本 `data/story_*.json`、`data/items*.json`、`data/phone.json` 里，每个 `{"zh": "…", "en": ""}` 都把 `en` 填上。
  - 范围包括台词、narr、选项、pick 的 label、objectives、hints、hotspot 的名字或提示、联系人名、物品的 name 和 desc。
  - 只要是给玩家看的字都算。
- 带 `"added": true` 的也照样翻，flag 保留。
- 只改 `"en": ""` 的值，用文本替换，别整份 JSON 重新序列化。格式、缩进、键的顺序都不许变，因为别的 agent 和作者也在改这些文件。
- 已经有英文的（speakers、物品名）不要改；觉得不好的，列出来交回。

## 已定的名字
- 晨 = Chen。鹿 = Deer，散文里写 the deer。弥洛 = Milo。妮芙 = Niff。阿汀 = Ting。
- 物品名照 `items.json` / `items_later.json` 里已有的 en，台词里提到物品要用同一个词，比如 Commuter Card、Blue Stone、Elephant Drawing、Communicator。
- 新遇到的专有名词（地名、东西、称呼），记到 `docs/en_glossary.md`。三个 agent 共用这一个文件：只往末尾追加，格式 `- 中文 = English（文件）`。追加前先读一遍，已经有的就照着用。

## 硬规则
- **晨的性别不定。** 英文里绝对不要用 he / she / him / her / his / hers 指晨。
  - 改写句子，或者用 Chen。万不得已才用 they。
  - 别人对晨说话用 you 就没问题。
- **失联的朋友是「她」**：she / her。
- 这个游戏要唯美、安静、零门槛。主题是冷漠和失去，不是焦虑。
  - 英文要短、口语、克制。不要华丽辞藻，不要加感叹号，不要把留白解释出来。
  - 好笑的地方保留好笑：弥洛嘴有点损，鹿天真。
  - 长度和中文差不多，别把一句短台词翻成两行长句，对话框很小。
  - 中文的口头语（「呗」「啊」「嘛」）按语气翻，不要硬塞 oh / well。
- 文字双关、中文特有的说法：意译，让英文读者能懂。实在丢了东西，在交回的报告里列出来。
- 不改剧本结构，不改 scene、不改 flag、不加不删台词。

## 代码里的界面字
- `scripts/` 里有些界面字是写死的中文，比如「↑ ↓  躲开碎石」、按钮文字。
  - 已经走 `I18n`（`scripts/i18n.gd` 的 `["English", "中文"]` 表）或者 `{"zh","en"}` 的不用管。
  - 只有中文、没有英文的，交给 B 处理：照现有的写法加英文。

## 检查（简单做，作者不要大测）
- 改完的每个 JSON 用 python `json.load` 解析一遍，确认没坏。
- 用 grep 确认 `"en": ""` 剩 0 个。
- 用 grep 确认没有用 he/she 指晨：搜 `\b(he|she|him|her|his)\b`，逐条看是不是在指晨。
- 不用跑游戏。最后由 B 跑一次 `--story_check`，确认能读。

## 分工
- **A**：`story_forest.json`、`items.json`、`items_later.json`、`phone.json`、`story_forest_sample.json`。
  - 注意：另一个 agent 正在改 `story_forest.json` 的走位。所以 A **先不要动 `story_forest.json`**：把译文写进 `docs/en_pending_forest.json`，格式 `[{"zh": 原文, "en": 译文}]`，按出现顺序排。
  - 同时写一个 `tools/apply_en.py`：用中文原文匹配那些 `"en": ""`，只替换它们的值，其余文本一个字节都不动。重复的原文给同一个译文。
  - 主对话通知以后，再跑这个脚本。
  - 其余文件直接改。
- **B**：`story_flight1.json`、`story_river.json`，加上代码里写死的界面字。最后跑一次 `--story_check`。
- **C**：`story_final.json`。

## 交回
用中文、简短地写：
- 改了哪些文件，填了多少条。
- 拿不准的译法，附原文和你的选择，最多 15 条。
- 觉得现有英文名不好的。
- 双关丢掉的地方。
