"""把译文填进剧本 JSON 里空着的 "en": ""（英文版翻译用，见 docs/en_translation_brief.md）。

    python3 tools/apply_en.py                        # 默认：docs/en_pending_forest.json → data/story_forest.json
    python3 tools/apply_en.py --dry                  # 只检查、打印统计，不写文件
    python3 tools/apply_en.py --pending P --target T # 别的文件也能用
    python3 tools/apply_en.py --extract T            # 把 T 里所有空着的 en 按出现顺序打成 [{"zh","en":""}]（打到标准输出）

规则：
- 只动 `"en": ""` 这几个字节：换成 `"en": "<译文>"`，其余文本一个字节都不改（不重新序列化）。
- 用同一个对象里的 "zh" 原文去 pending 表里找译文；同一句原文出现几次都给同一个译文。
- zh 也是空的（比如 burn_note 还没写）就跳过。
- pending 里找不到的原文、pending 里没用上的条目都打印出来（另一个 agent 改过剧本时用来对账）。
- 写完再 json.load 一遍，并确认除了这几处以外和原文完全一样。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Scanner:
    """极简 JSON 扫描器：只为了拿到每个对象里 "zh" 的值和 "en" 值在原文里的位置。"""

    def __init__(self, text: str):
        self.t = text
        self.i = 0
        self.hits: list[tuple[int, int, str]] = []  # (en 值起点, 终点, zh 原文)：en 为空的

    def ws(self):
        t = self.t
        while self.i < len(t) and t[self.i] in " \t\r\n":
            self.i += 1

    def string(self) -> tuple[str, int, int]:
        start = self.i
        assert self.t[self.i] == '"', self.i
        self.i += 1
        while True:
            c = self.t[self.i]
            if c == "\\":
                self.i += 2
                continue
            self.i += 1
            if c == '"':
                break
        end = self.i
        return json.loads(self.t[start:end]), start, end

    def value(self):
        self.ws()
        c = self.t[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            self.i += 1
            self.ws()
            if self.t[self.i] == "]":
                self.i += 1
                return None
            while True:
                self.value()
                self.ws()
                c = self.t[self.i]
                self.i += 1
                if c == "]":
                    return None
                assert c == ",", self.i
        if c == '"':
            return self.string()
        # 数字 / true / false / null

        while self.i < len(self.t) and self.t[self.i] not in ",]}\r\n\t ":
            self.i += 1
        return None

    def obj(self):
        self.i += 1
        fields: dict[str, object] = {}
        self.ws()
        if self.t[self.i] == "}":
            self.i += 1
            return None
        while True:
            self.ws()
            key, _, _ = self.string()
            self.ws()
            assert self.t[self.i] == ":", self.i
            self.i += 1
            fields[key] = self.value()
            self.ws()
            c = self.t[self.i]
            self.i += 1
            if c == "}":
                break
            assert c == ",", self.i
        en, zh = fields.get("en"), fields.get("zh")
        if isinstance(en, tuple) and en[0] == "" and isinstance(zh, tuple):
            self.hits.append((en[1], en[2], zh[0]))
        return None


def scan(text: str) -> list[tuple[int, int, str]]:
    s = Scanner(text)
    s.value()
    return sorted(s.hits)


def extract(target: Path):
    text = target.read_text(encoding="utf-8")
    seen, out = set(), []
    for _, _, zh in scan(text):
        if zh and zh not in seen:
            seen.add(zh)
            out.append({"zh": zh, "en": ""})
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


def apply(pending: Path, target: Path, dry: bool) -> int:
    table: dict[str, str] = {}
    for row in json.loads(pending.read_text(encoding="utf-8")):
        zh, en = row["zh"], row["en"]
        if not en:
            continue
        if zh in table and table[zh] != en:
            print(f"! pending 里同一句原文有两个译文，用第一个：{zh!r}")
            continue
        table[zh] = en

    raw = target.read_bytes()
    text = raw.decode("utf-8")
    json.loads(text)  # 原文件先得是好的
    hits = scan(text)

    filled, skipped_empty, missing, used = 0, 0, [], set()
    pieces, last = [], 0
    for start, end, zh in hits:
        if not zh:
            skipped_empty += 1
            continue
        en = table.get(zh)
        if en is None:
            missing.append(zh)
            continue
        assert text[start:end] == '""'
        pieces.append(text[last:start])
        pieces.append(json.dumps(en, ensure_ascii=False))
        last = end
        filled += 1
        used.add(zh)
    pieces.append(text[last:])
    new = "".join(pieces)

    json.loads(new)  # 写完还得是好的
    # 除了被填的这几处，其余一个字节都不许变
    strict_ok = _strict_same(text, new, hits, used, table)

    unused = [zh for zh in table if zh not in used]
    print(f"{target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}: "
          f"空着的 en {len(hits)} 处，填了 {filled}，zh 也是空的跳过 {skipped_empty}，没找到译文 {len(missing)}")
    for zh in missing:
        print(f"  没找到译文：{zh!r}")
    if unused:
        print(f"  pending 里没用上 {len(unused)} 条（剧本里这句可能改过或删了）：")
        for zh in unused:
            print(f"    {zh!r}")
    if not strict_ok:
        print("! 字节校验失败，不写文件")
        return 1
    if dry:
        print("（--dry：没写文件）")
    elif filled:
        target.write_bytes(new.encode("utf-8"))
        print("已写入。")
    return 0


def _strict_same(old: str, new: str, hits, used, table) -> bool:
    """按位置逐段比：old 里每个被填的 "" 之外的片段，在 new 里必须一模一样、顺序一样。"""
    oi = ni = 0
    for start, end, zh in hits:
        if zh not in used:
            continue
        seg = old[oi:start]
        if new[ni:ni + len(seg)] != seg:
            return False
        ni += len(seg)
        rep = json.dumps(table[zh], ensure_ascii=False)
        if new[ni:ni + len(rep)] != rep:
            return False
        ni += len(rep)
        oi = end
    return old[oi:] == new[ni:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", default=str(ROOT / "docs/en_pending_forest.json"))
    ap.add_argument("--target", default=str(ROOT / "data/story_forest.json"))
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--extract", metavar="TARGET")
    a = ap.parse_args()
    if a.extract:
        extract(Path(a.extract))
        return 0
    return apply(Path(a.pending), Path(a.target), a.dry)


if __name__ == "__main__":
    sys.exit(main())
