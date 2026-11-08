#!/bin/bash
# 导出《云》的 B 站 Toy 网页版并打 zip（照 Toy 手册附录 K，Linger / 校园伪人的 bilibili/export_web.sh 改）。
#
#   bash bilibili/export.sh   -> ../导出/B站/云_bilibili_web/（导出目录）和 ../导出/B站/云_bilibili_web.zip（上传 Toy 用这个 zip）
#
# 做的事：headless 导入（新画的图要先有 .import 才会进包）→ 导出预设「Web」→ 给 index.js 打三个补丁（下载出错重试、
# 读存档超时、主包不多拷一份）→ 把 bilibili/VERSION + 北京时间写进 shell.html 的 __CLOUD_VERSION__ → 引擎和资源包各压一份
# *.gz.bin（Toy 的 CDN 不压缩 .wasm/.pck，shell.html 在浏览器里边下边解压，原文件留着兜底）→ 打 zip → 报体积和包里最大的文件。
# 每次上传前先把 bilibili/VERSION 升一号（一次上传只升一次，手册第一节第 4 条）。
# 和 tools/gt_headless.sh 用同一把锁：别的会话正在跑 headless Godot 时在这里排队，不会两个 Godot 同时写 .godot/ 的导入缓存。
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT="/Applications/Godot.app/Contents/MacOS/Godot"
LOCK=(/usr/bin/lockf -k /tmp/the_cloud_godot.lock)
OUT="../导出/B站/云_bilibili_web"
ZIP="../导出/B站/云_bilibili_web.zip"
LOGS="../导出/B站/logs"
TPL="$HOME/Library/Application Support/Godot/export_templates/4.7.2.stable/web_nothreads_release.zip"
[ -x "$GODOT" ] || { echo "找不到 Godot：$GODOT"; exit 1; }
[ -f "$TPL" ] || { echo "没装 Godot 4.7.2 的 Web 导出模板：$TPL（编辑器里 编辑器 → 管理导出模板 装一下）"; exit 1; }
grep -q 'name="Web"' export_presets.cfg || { echo "export_presets.cfg 里没有「Web」预设"; exit 1; }
mkdir -p "$LOGS"
rm -rf "${OUT:?}"
mkdir -p "$OUT"

echo "== 导入（新资源补 .import 和缓存）"
"${LOCK[@]}" "$GODOT" --headless --path . --import > "$LOGS/import.log" 2>&1 || echo "（导入有报错，看 $LOGS/import.log；继续导出）"
echo "== 导出 Web 预设"
"${LOCK[@]}" "$GODOT" --headless --path . --export-release "Web" "$OUT/index.html" > "$LOGS/export.log" 2>&1 || { tail -30 "$LOGS/export.log"; echo "导出失败，全文在 $LOGS/export.log"; exit 1; }
grep -i "error" "$LOGS/export.log" | grep -v "^$" | head -20 || true
[ -f "$OUT/index.pck" ] && [ -f "$OUT/index.wasm" ] || { echo "导出目录里没有 index.pck / index.wasm"; exit 1; }

# Godot 下载器的漏洞（寻找伪人 2026-10-15，玩家卡在 0%）：边下边统计进度的那段读数据出错时把错误吞了，流既不结束也不报错，
# 网络半路断一下就永远卡住，也不会重试。给它补上「出错就把错误传出去」，Godot 才会重下（最多 4 遍）。
python3 - "$OUT/index.js" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = """onloadprogress(reader, controller).then(function () {
					controller.close();
				});"""
new = """onloadprogress(reader, controller).then(function () {
					controller.close();
				}, function (err) {
					controller.error(err);
				});"""
if old not in s:
    sys.exit("index.js 里找不到下载器那段代码（Godot 版本变了？），补丁没打上")
open(p, "w").write(s.replace(old, new))
print("index.js：下载器出错重试的补丁已打上")
PY
# 启动时读存档（IndexedDB → 内存）没有超时（校园伪人 2026-10-24，iPhone 卡死后一直停在「正在启动」）：
# 8 秒没回话就当这次没有存档、照常进游戏（window.cloudIdbStuck = true）。
python3 - "$OUT/index.js" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "return new Promise(function(resolve,reject){FS.syncfs(true,function(err){"
new = ("return new Promise(function(resolve,reject){var cloudDone=false;var cloudT=setTimeout(function(){if(cloudDone)return;cloudDone=true;"
       "GodotFS._mount_points=[];GodotFS._idbfs=false;GodotRuntime.print('IndexedDB 8 秒没回话：这次不读存档');"
       "try{window.cloudIdbStuck=true}catch(e){}resolve(new Error('IndexedDB timeout'))},8000);"
       "FS.syncfs(true,function(err){if(cloudDone)return;cloudDone=true;clearTimeout(cloudT);")
if s.count(old) != 1:
    sys.exit("index.js 里找不到读存档那段代码（Godot 版本变了？），超时补丁没打上")
open(p, "w").write(s.replace(old, new))
print("index.js：读存档 8 秒超时的补丁已打上")
PY
# 主包交给引擎时（copy_to_fs）别再复制一份（校园伪人 1.7：有玩家启动时内存不够）：传 canOwn: true，文件系统直接接手这块内存。
python3 - "$OUT/index.js" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "FS.writeFile(path,new Uint8Array(buffer))}"
new = "FS.writeFile(path,new Uint8Array(buffer),{canOwn:true})}"
if s.count(old) != 1:
    sys.exit("index.js 里找不到 copy_to_fs 的 FS.writeFile（Godot 版本变了？），补丁没打上")
open(p, "w").write(s.replace(old, new))
print("index.js：主包交给引擎时不再复制一份")
PY
# 引擎模板必须是关掉 wasm 异常处理和 SIMD 的精简模板（手册附录 Q，bilibili/web_nothreads_release_slim.zip，从 Linger 拷来的
# 4.7.2 版：只有 2D、无线程、没有 3D / RegEx / 导航 / 多人 等模块，见 Linger/linger_bilibili/bilibili/custom.py）。
# 官方模板带异常处理段，老安卓手机到 100% 报 unexpected section <Tag>：这里每次导出都查，有就不让过。
python3 - "$OUT/index.wasm" <<'PY'
import sys
b = open(sys.argv[1], 'rb').read()
i, ids = 8, set()
while i < len(b):
    sid = b[i]; i += 1
    n = s = 0
    while True:
        x = b[i]; i += 1; n |= (x & 0x7f) << s; s += 7
        if x < 0x80:
            break
    ids.add(sid); i += n
if 13 in ids:
    sys.exit("index.wasm 里有 wasm 异常处理段（tag）：引擎模板是官方的或旧的，老安卓手机打不开。预设 custom_template/release 要指向 bilibili/web_nothreads_release_slim.zip")
else:
    print("index.wasm：没有异常处理段，老手机能打开")
PY

# 加载界面、标题、设置里显示的版本号：VERSION + 北京时间，一眼看出线上是不是新版
VERSION="v$(tr -d '[:space:]' < bilibili/VERSION) · $(TZ=Asia/Shanghai date '+%m.%d %H:%M')"
sed -i '' "s/__CLOUD_VERSION__/$VERSION/" "$OUT/index.html"
grep -q "__CLOUD_VERSION__" "$OUT/index.html" && { echo "版本号没替换干净"; exit 1; }
echo "版本号：$VERSION"
# 加载界面的像素字体：游戏 UI 的字只留页面上用到的字，嵌进 index.html（作者 11-07：加载页的「云」要像素体）
python3 bilibili/加载界面.py "$OUT"
grep -q "__CLOUD_FONT__" "$OUT/index.html" && { echo "字体没嵌进去"; exit 1; }
# 封面图（有就铺在加载界面上；没有 shell.html 只显示字）
[ -f bilibili/splash.webp ] && cp bilibili/splash.webp "$OUT/splash.webp"

gzip -9 -c "$OUT/index.wasm" > "$OUT/index.wasm.gz.bin"
gzip -9 -c "$OUT/index.pck" > "$OUT/index.pck.gz.bin"
rm -f "$ZIP"
(cd "$OUT" && zip -q -r "../$(basename "$ZIP")" . -x '.DS_Store')

echo "== 导出目录"
ls -la "$OUT"
echo "== 包里最大的 20 个文件"
python3 bilibili/pck_list.py "$OUT/index.pck" 20
ZIP_MB=$(du -m "$ZIP" | cut -f1)
echo "== zip：$ZIP  ${ZIP_MB}MB（Toy 上限 140MB，新账号 50MB）"
[ "$ZIP_MB" -gt 140 ] && echo "！！超过 140MB，传不上去"
[ "$ZIP_MB" -gt 50 ] && echo "！！超过 50MB，新账号传不上去"
true
