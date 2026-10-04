import http from 'node:http';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.wasm': 'application/wasm',
  '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp',
  '.svg': 'image/svg+xml', '.woff': 'font/woff', '.woff2': 'font/woff2' };
const server = http.createServer(async (request, response) => {
  try {
    if (!['GET', 'HEAD'].includes(request.method)) { response.writeHead(405).end(); return; }
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const target = path.resolve(root, '.' + (pathname.endsWith('/') ? pathname + 'index.html' : pathname));
    const relative = path.relative(root, target);
    if (relative.startsWith('..') || path.isAbsolute(relative)) { response.writeHead(403).end(); return; }
    const info = await stat(target);
    if (!info.isFile()) { response.writeHead(404).end(); return; }
    response.writeHead(200, { 'Content-Type': types[path.extname(target)] || 'application/octet-stream',
      'Content-Length': info.size, 'X-Content-Type-Options': 'nosniff' });
    if (request.method === 'HEAD') response.end();
    else createReadStream(target).on('error', () => response.destroy()).pipe(response);
  } catch { response.writeHead(404).end(); }
});
server.listen(0, '127.0.0.1', () => {
  const url = `http://127.0.0.1:${server.address().port}/`;
  console.log('IGRIS_CHESS_URL=' + url);
  console.log('Cierra esta ventana para detener el juego local.');
  if (process.platform === 'win32' && !process.argv.includes('--no-open')) {
    spawn('rundll32.exe', ['url.dll,FileProtocolHandler', url], { windowsHide: true, stdio: 'ignore' });
  }
});
process.on('SIGINT', () => server.close(() => process.exit(0)));
process.on('SIGTERM', () => server.close(() => process.exit(0)));