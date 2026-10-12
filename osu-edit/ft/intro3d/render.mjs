// usage:
//   node render.mjs stills <outdir> <t1,t2,...> [text=1]
//   node render.mjs video <out.mp4> <fps> <t_end> [text=1]
import { chromium } from 'playwright-core';
import { spawn } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';

const root = path.dirname(new URL(import.meta.url).pathname);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const f = path.normalize(path.join(root, u === '/' ? 'index.html' : u));
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const [mode, out, a3, a4, a5] = process.argv.slice(2);
const text = mode === 'stills' ? (a4 ?? '1') : (a5 ?? '1');

const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-proxy-server'],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('console', (m) => console.log('[page]', m.text()));
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${port}/index.html?text=${text}`);
await page.waitForFunction(() => window.READY === true, null, { timeout: 120000 });

if (mode === 'stills') {
  fs.mkdirSync(out, { recursive: true });
  if (a5) await page.evaluate((c) => { window.CAM = JSON.parse(c); }, a5);
  for (const ts of a3.split(',')) {
    const t = parseFloat(ts);
    await page.evaluate((t) => window.renderAt(t), t);
    await page.screenshot({ path: path.join(out, `t${t.toFixed(2)}.png`) });
    console.log('still', t);
  }
} else {
  const fps = parseFloat(a3), tEnd = parseFloat(a4);
  const n = Math.round(tEnd * fps);
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await page.evaluate((t) => window.renderAt(t), i / fps);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 60 === 0) console.log(`frame ${i}/${n} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log('done', out);
}
await browser.close();
server.close();
