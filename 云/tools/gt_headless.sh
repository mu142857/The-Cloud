#!/bin/zsh
# tools/gt_headless.sh 秒数 日志文件 -- 参数... ：在锁里只跑 headless 的 Godot，超时直接杀掉。
# 「--」要原样传给 Godot（它后面的才是 OS.get_cmdline_user_args()），脚本不能吃掉它。
# 11-05 原来放在临时目录的 gt.sh 随目录没了，挪进项目。作者醒着时只许这样跑（不开窗口、不截图）；
# 要开窗口截图的运行不走这个脚本，留到作者说「去测试」以后再单独做。
sec=$1; log=$2; shift 2
cd "$(dirname "$0")/.."
exec /usr/bin/lockf -k /tmp/the_cloud_godot.lock /bin/zsh -c '
/Applications/Godot.app/Contents/MacOS/Godot --headless --audio-driver Dummy --fixed-fps 60 --path . "${@:3}" > "$2" 2>&1 & p=$!
( sleep $1; kill -9 $p 2>/dev/null && echo "GT_TIMEOUT $1s" >> "$2" ) & w=$!
wait $p; kill $w 2>/dev/null; true' _ $sec $log "$@"
