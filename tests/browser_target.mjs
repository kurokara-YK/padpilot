// Local, disposable Chrome page for keyboard_probe.py. No external site is opened.
import {spawn, execFileSync} from 'node:child_process';
import {readFileSync, writeFileSync, renameSync, existsSync} from 'node:fs';
import {join} from 'node:path';

const dir = process.argv[2];
const title = `PADPILOT PROBE ${dir.split('/').at(-1)}`;
const html = `<title>${title}</title><label>Keyboard test <input id="entry" autofocus></label>
<button id="outside">Non-text focus target</button><script>
window.activations=[]; entry.addEventListener('keydown',e=>{if(e.key==='Enter')activations.push(entry.value)});
</script>`;
const browser = spawn('/usr/bin/google-chrome', [
    `--user-data-dir=${join(dir, 'chrome-profile')}`, '--remote-debugging-port=0',
    '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--force-renderer-accessibility', '--window-position=100,200', '--window-size=800,500',
    `data:text/html;charset=utf-8,${encodeURIComponent(html)}`,
], {stdio: 'ignore'});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const portFile = join(dir, 'chrome-profile', 'DevToolsActivePort');
const until = Date.now() + 20000;
while (!existsSync(portFile)) {
    if (browser.exitCode !== null || Date.now() > until) throw Error('Chrome startup failed');
    await sleep(100);
}
const port = readFileSync(portFile, 'utf8').split('\n')[0];
let page;
while (!page) {
    const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    page = pages.find(p => p.title === title);
    if (Date.now() > until) throw Error('Chrome test page not found');
    await sleep(100);
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {ws.onopen = resolve; ws.onerror = reject;});
let nextId = 0;
const pending = new Map();
ws.onmessage = event => {
    const msg = JSON.parse(event.data);
    if (pending.has(msg.id)) {
        const {resolve, reject} = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(Error(JSON.stringify(msg.error))); else resolve(msg.result);
    }
};
function call(method, params = {}) {
    return new Promise((resolve, reject) => {
        const id = ++nextId; pending.set(id, {resolve, reject});
        ws.send(JSON.stringify({id, method, params}));
    });
}
async function evaluate(expression) {
    const result = await call('Runtime.evaluate', {expression, returnByValue: true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
}
await call('Page.bringToFront');
await evaluate('entry.focus()');
let wid;
while (!wid) {
    const ids = execFileSync('xprop', ['-root', '_NET_CLIENT_LIST'], {encoding: 'utf8'}).match(/0x[0-9a-f]+/g) ?? [];
    for (const id of ids) {
        const name = execFileSync('xprop', ['-id', id, '_NET_WM_NAME'], {encoding: 'utf8'});
        if (name.includes(`"${title} - Google Chrome"`)) wid = Number(id);
    }
    if (Date.now() > until) throw Error('Chrome X11 window not found');
    await sleep(100);
}
let reset = 0, focus = '';
while (browser.exitCode === null) {
    if (existsSync(join(dir, 'reset'))) {
        const value = Number(readFileSync(join(dir, 'reset'), 'utf8'));
        if (value !== reset) {await evaluate("entry.value = ''"); reset = value;}
    }
    if (existsSync(join(dir, 'focus'))) {
        const value = readFileSync(join(dir, 'focus'), 'utf8');
        if (value !== focus) {await evaluate(`${value === 'entry' ? 'entry' : 'outside'}.focus()`); focus = value;}
    }
    const state = await evaluate('({text:entry.value,activations:window.activations})');
    writeFileSync(join(dir, 'target.tmp'), JSON.stringify({...state, wid, reset, focus}));
    renameSync(join(dir, 'target.tmp'), join(dir, 'target.json'));
    await sleep(50);
}
