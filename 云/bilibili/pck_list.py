#!/usr/bin/env python3
"""列出 Godot 4 的 .pck 里有什么：最大的 N 个文件、按顶层文件夹合计、按后缀合计。

    python3 bilibili/pck_list.py ../导出/B站/云_bilibili_web/index.pck 20          最大的 20 个 + 合计
    python3 bilibili/pck_list.py ../导出/B站/云_bilibili_web/index.pck 0 docs/    只列路径里带 docs/ 的

bilibili/export.sh 导出完自动跑一遍。查某张图有没有被 exclude_filter 去掉：搜它导入后的名字（<图名>.png-<哈希>.ctex）。
pck 格式：GDPC、版本（2 = 4.0~4.3，3/4 = 4.4 起，目录挪到 dir_offset、路径不带 res://）、引擎版本 ×3、flags、file_base、保留位、文件数，
然后每条 路径长、路径、偏移、大小、md5、flags。
"""
import struct
import sys
from collections import defaultdict


def entries(path):
    b = open(path, "rb").read()
    if b[:4] != b"GDPC":
        sys.exit("不是 pck（没有 GDPC 头）")
    ver, major, minor, patch, flags = struct.unpack_from("<5I", b, 4)
    file_base = struct.unpack_from("<Q", b, 24)[0]
    pos = 32

    def parse_dir(p):
        n = struct.unpack_from("<I", b, p)[0]
        p += 4
        if n <= 0 or n > 200000:
            raise ValueError
        out = []
        for _ in range(n):
            ln = struct.unpack_from("<I", b, p)[0]
            p += 4
            if ln <= 0 or ln > 4096:
                raise ValueError
            name = b[p:p + ln].rstrip(b"\0").decode("utf-8")   # 格式 4（4.5 起）不带 res:// 前缀
            if not name or not name.isprintable():
                raise ValueError
            p += ln
            ofs, size = struct.unpack_from("<QQ", b, p)
            p += 16 + 16 + 4   # ofs, size, md5, flags
            out.append((name, size))
        return out

    tries = []
    if ver >= 3:
        dir_offset = struct.unpack_from("<Q", b, pos)[0]
        tries.append(dir_offset)
        tries.append(pos + 8 + 14 * 4)
    tries.append(pos + 16 * 4)
    tries.append(pos + 8 + 16 * 4)
    for t in tries:
        try:
            return (ver, f"{major}.{minor}.{patch}", flags), parse_dir(t)
        except (ValueError, struct.error, UnicodeDecodeError):
            continue
    sys.exit(f"看不懂这个 pck 的目录（格式版本 {ver}）")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    needle = sys.argv[3] if len(sys.argv) > 3 else ""
    (ver, godot, flags), files = entries(sys.argv[1])
    if needle:
        for name, size in sorted(files):
            if needle in name:
                print(f"{size:>12,}  {name}")
        return
    total = sum(s for _, s in files)
    print(f"pck 格式 {ver}，Godot {godot}，{len(files)} 个文件，共 {total / 1e6:.1f} MB")
    print(f"-- 最大的 {top} 个")
    for name, size in sorted(files, key=lambda x: -x[1])[:top]:
        print(f"{size / 1e6:>8.2f} MB  {name}")
    by_dir = defaultdict(int)
    by_ext = defaultdict(int)
    for name, size in files:
        rel = name[len("res://"):] if name.startswith("res://") else name
        parts = rel.split("/")
        key = parts[0] if len(parts) == 1 else parts[0] + "/" + (parts[1] if parts[0] in ("art", "audio", ".godot") and len(parts) > 2 else "")
        by_dir[key.rstrip("/")] += size
        ext = rel.rsplit(".", 1)[-1] if "." in rel else "(无后缀)"
        by_ext[ext] += size
    print("-- 按文件夹合计")
    for k, v in sorted(by_dir.items(), key=lambda x: -x[1])[:25]:
        print(f"{v / 1e6:>8.2f} MB  {k}")
    print("-- 按后缀合计")
    for k, v in sorted(by_ext.items(), key=lambda x: -x[1])[:12]:
        print(f"{v / 1e6:>8.2f} MB  .{k}")


if __name__ == "__main__":
    main()
