// Static server for the demo, with the headers the PoC is actually about.
//
// It speaks BOTH transports the Web Profile frame travels over:
//
//   * `Content-Type: application/cubrim` — a direct request for a `.cbr` file,
//     the transport CUBR-0077 specifies. The page decodes explicitly.
//   * `Content-Encoding: cbm` — the epic's namesake (CUBR-0072). When the
//     client lists `cbm` in `Accept-Encoding` and a precompressed sibling
//     `<file>.cbr` exists, the resource itself is served under its own
//     `Content-Type` with `Content-Encoding: cbm`, and falls back to identity
//     for every other client. Negotiation lives in `encoding.mjs`.
//
// `Vary: Accept-Encoding` is sent on every resource that has a `.cbr` variant,
// whichever representation is chosen — without it a shared cache would hand
// the cbm bytes to a client that never asked for them.
//
// It also applies a real CSP, including `'wasm-unsafe-eval'` in `script-src` —
// without it a modern browser refuses to instantiate the module, which is
// exactly the kind of deployment detail a PoC exists to surface.
//
// Usage: node serve.mjs <root-dir> [port]

import { createServer } from 'node:http';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { pathToFileURL } from 'node:url';
import { negotiate } from './encoding.mjs';

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

/** The registry-facing content-coding token (working name `cubrim`). */
const CODING = 'cbm';

/**
 * Build the demo server for `root`. Exported so the end-to-end tests can run
 * the real request path on an ephemeral port instead of re-implementing it.
 */
export function createDemoServer(root) {
  return createServer(async (req, res) => {
    try {
      // The demo POSTs its measurements here when it finishes, so a headless
      // run reads a file instead of racing the page's async work with a DOM
      // dump.
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

      const headers = {
        'content-type': TYPES[extname(path)] ?? 'application/octet-stream',
        'content-security-policy': CSP,
        'x-content-type-options': 'nosniff',
        'cache-control': 'no-store',
      };

      // Content-Encoding negotiation: only for resources that are not
      // themselves frames and that have a precompressed `.cbr` sibling.
      let bodyPath = path;
      if (extname(path) !== '.cbr' && (await isFile(`${path}.cbr`))) {
        headers.vary = 'Accept-Encoding';
        const coding = negotiate(req.headers['accept-encoding'], [CODING]);
        if (coding === null) {
          res.writeHead(406, {
            'content-type': 'text/plain',
            vary: 'Accept-Encoding',
          });
          res.end('no acceptable content-coding');
          return;
        }
        if (coding === CODING) {
          headers['content-encoding'] = CODING;
          bodyPath = `${path}.cbr`;
        }
      }

      const body = await readFile(bodyPath);
      headers['content-length'] = body.length;
      res.writeHead(200, headers);
      res.end(body);
    } catch {
      res.writeHead(404, { 'content-type': 'text/plain' });
      res.end('not found');
    }
  });
}

async function isFile(path) {
  try {
    return (await stat(path)).isFile();
  } catch {
    return false;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = process.argv[2] ?? '.';
  const port = Number(process.argv[3] ?? 8077);
  createDemoServer(root).listen(port, '127.0.0.1', () => {
    console.log(
      `serving ${root} on http://127.0.0.1:${port}/ ` +
        '(cbr as application/cubrim, Content-Encoding: cbm negotiated, CSP on)',
    );
  });
}
