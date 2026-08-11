// Static server for the demo, with the headers the PoC is actually about.
//
// Two things it gets right that a generic static server does not:
//   * `.cbr` files are served as `Content-Type: application/cubrim`, which is
//     the transport CUBR-0077 specifies (no `Content-Encoding` negotiation);
//   * a real CSP is applied, including `'wasm-unsafe-eval'` in `script-src` —
//     without it a modern browser refuses to instantiate the module, which is
//     exactly the kind of deployment detail a PoC exists to surface.
//
// Usage: node serve.mjs <root-dir> [port]

import { createServer } from 'node:http';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const root = process.argv[2] ?? '.';
const port = Number(process.argv[3] ?? 8077);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.wasm': 'application/wasm',
  '.json': 'application/json',
  '.css': 'text/css; charset=utf-8',
  '.map': 'application/json',
  '.woff2': 'font/woff2',
  '.cbr': 'application/cubrim',
};

const CSP = [
  "default-src 'self'",
  // 'wasm-unsafe-eval' is required for WebAssembly.instantiate under CSP.
  "script-src 'self' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
].join('; ');

createServer(async (req, res) => {
  try {
    // The demo POSTs its measurements here when it finishes, so a headless run
    // reads a file instead of racing the page's async work with a DOM dump.
    if (req.method === 'POST' && req.url === '/__results') {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const body = Buffer.concat(chunks);
      await writeFile(join(root, 'browser-results.json'), body);
      res.writeHead(204).end();
      return;
    }
    const url = new URL(req.url, `http://${req.headers.host}`);
    const rel = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '');
    const path = join(root, rel === '/' ? 'demo.html' : rel);
    const info = await stat(path);
    if (!info.isFile()) throw new Error('not a file');
    const body = await readFile(path);
    res.writeHead(200, {
      'content-type': TYPES[extname(path)] ?? 'application/octet-stream',
      'content-length': body.length,
      'content-security-policy': CSP,
      'x-content-type-options': 'nosniff',
      'cache-control': 'no-store',
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain' });
    res.end('not found');
  }
}).listen(port, '127.0.0.1', () => {
  console.log(`serving ${root} on http://127.0.0.1:${port}/ (cbr as application/cubrim, CSP on)`);
});
