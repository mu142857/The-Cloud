#!/bin/zsh
# 一条命令跑全部自动检查（docs/QA_自动检查.md）：字量框、四章剧本检查、自动玩三条路（主线+全部支线连到终章 / 孩子线 / 只走主线）边玩边看。
# 全部 --headless，不开窗口、不抢焦点。用法：tools/qa_all.sh [日志目录]（默认 /tmp/the_cloud_qa）。跑完最后打印每类几条。
cd "$(dirname "$0")/.."
OUT=${1:-/tmp/the_cloud_qa}
mkdir -p "$OUT"
GODOT=/Applications/Godot.app/Contents/MacOS/Godot
run() {   # run 秒 日志名 参数…（和别的测试共用一把锁，超时杀掉）
  local sec=$1 log="$OUT/$2.log"; shift 2
  /usr/bin/lockf -k /tmp/the_cloud_godot.lock /bin/zsh -c '
  "$3" --headless --audio-driver Dummy --fixed-fps 60 --path . "${@:4}" > "$2" 2>&1 & p=$!
  ( sleep $1; kill -9 $p 2>/dev/null && echo "GT_TIMEOUT $1s" >> "$2" ) & w=$!
  wait $p; kill $w 2>/dev/null; true' _ $sec "$log" "$GODOT" "$@"
}
run 90 text -- --qa_text
for c in forest flight1 river final; do run 90 check_$c -- --chapter=$c --story_check; done
run 480 live_all -- --story_auto --story_chain --qa_live
run 240 live_child -- --story_auto --qa_live --auto_to=c1_child
run 240 live_main -- --story_auto --qa_live --main_only
echo "==== 字量框（qa_text）"; grep -h "^QA_TEXT" "$OUT/text.log"
echo "==== 剧本检查（不算 info）"
for c in forest flight1 river final; do grep -h "^STORY_CHECK" "$OUT/check_$c.log" | grep -v "STORY_CHECK info"; done
echo "==== 边玩边看（每章一行）"
grep -h "^QA_LIVE_SUMMARY\|^QA_MOTION_SUMMARY\|^CHAPTER\|STORY_STUCK\|SCRIPT ERROR\|GT_TIMEOUT" "$OUT"/live_*.log
echo "==== 具体哪几条"
grep -h "^QA_OVERLAP\|^QA_OFFSCREEN\|^QA_DLG\|^QA_JUMP\|^QA_CAMJUMP\|^QA_PROP\|^QA_POPIN" "$OUT"/live_*.log | sort -u
