// 无界面 Chrome 打开网页版导出，把游戏的控制台输出存成文件，看到指定的日志（或到时）就截一张图退出。
// 照 校园伪人/campus/bilibili/测卡顿.mjs 改。作者醒着也能跑：不开任何窗口。
//   node bilibili/跑网页.mjs <网址> <最多秒数> <输出日志> [截图路径] [停下的正则]
//   例：先在导出目录 python3 -m http.server 8765，把 index.html 复制一份、GODOT_CONFIG 的 "args" 填上
//       ["--","--chapter=flight1","--story_auto","--story_chain","--qa_live"]（手册第七节「导出一份测试包」做法），再
//       node bilibili/跑网页.mjs http://127.0.0.1:8765/_test.html 480 ../导出/B站/logs/x.log ../导出/B站/logs/x.png 'STORY_SCENE start_river|BACK_TO_TITLE'
// Chrome 自带的 --screenshot --timeout 不行：页面 load 一结束就截图退出，游戏才跑了几秒。
import { spawn } from 'node:child_process';
import { writeFileSync, appendFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url, secs = '300', out = 'web.log', shot = '', stopRe = ''] = process.argv.slice(2);
const stop = stopRe ? new RegExp(stopRe) : null;
const port = 9333 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(process.env.TMPDIR || tmpdir(), 'chr-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-timer-throttling',
  '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
  '--autoplay-policy=no-user-gesture-required', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--disable-gpu',
  '--window-size=1440,810', 'about:blank'], { stdio: 'ignore' });

writeFileSync(out, `# ${url} 最多 ${secs}s 停于 /${stopRe}/\n`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(200); }
}
const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
const t0 = Date.now();
let hit = false;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
  if (m.method === 'Runtime.consoleAPICalled') {
    const text = m.params.args.map((a) => a.value ?? a.description ?? '').join(' ');
    appendFileSync(out, `[${((Date.now() - t0) / 1000).toFixed(1)}s] ${text}\n`);
    if (stop && stop.test(text)) { hit = true; }
  } else if (m.method === 'Runtime.exceptionThrown') {
    appendFileSync(out, `[EXC] ${JSON.stringify(m.params.exceptionDetails).slice(0, 400)}\n`);
  }
});
await send('Runtime.enable');
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 810, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
const deadline = t0 + Number(secs) * 1000;
while (Date.now() < deadline && !hit) { await sleep(500); }
if (hit) { await sleep(6000); }   // 看到想要的日志以后再等几秒，让画面切过去再截
if (shot) {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  if (r && r.data) { writeFileSync(shot, Buffer.from(r.data, 'base64')); }
}
appendFileSync(out, `# done ${hit ? '（看到了停下的日志）' : '（到时）'} ${((Date.now() - t0) / 1000).toFixed(0)}s\n`);
ws.close();
chrome.kill();
process.exit(0);
