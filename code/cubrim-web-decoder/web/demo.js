// Demo driver for the Cubrim Web Profile WASM decoder.
//
// External rather than inline on purpose: the demo is served under a strict
// CSP (script-src 'self' 'wasm-unsafe-eval'), which blocks inline scripts. That
// is the correct production posture, so the page is built to satisfy it instead
// of the policy being loosened to fit the page.

import CubrimDecoder from './cubrim.js';

const ASSETS = [
  'tailwind.css',
  'html-large-web-codec-v2.html',
  'html-medium-home-v2.html',
  'magic-string.umd.js',
  'sourcemap-codec.umd.js',
  'resolve-uri.umd.js',
  'json-api-large-world-benchmark-v2.json',
  'json-api-medium-web-benchmark-v2.json',
  'json-api-small-hypotheses-v2.json',
  'magic-string.umd.js.map',
  'sourcemap-codec.umd.js.map',
  'inter-latin.medium.woff2',
];

const tbody = document.querySelector('#results tbody');
const summary = document.getElementById('summary');
const results = [];

async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

const cubrim = await CubrimDecoder.load('./cubrim_web_decoder.wasm');

for (const name of ASSETS) {
  // Served as application/cubrim; the page, not the browser, decodes it.
  const response = await fetch(`./fixtures/${name}.cbr`);
  const frame = new Uint8Array(await response.arrayBuffer());

  // performance.now() is deliberately coarsened by browsers (~100 us, or 1 ms
  // without cross-origin isolation), which would quantise a sub-millisecond
  // decode into nonsense. Amortise: warm up, then time a whole loop and divide.
  const WARMUPS = 3;
  const REPEATS = 25;
  for (let i = 0; i < WARMUPS; i += 1) cubrim.cubrimDecode(frame, 64 << 20);
  const t0 = performance.now();
  let decoded;
  for (let i = 0; i < REPEATS; i += 1) decoded = cubrim.cubrimDecode(frame, 64 << 20);
  const ms = (performance.now() - t0) / REPEATS;

  // Verify against the original bytes, so no number is reported for a decode
  // that did not reproduce the asset.
  const original = new Uint8Array(await (await fetch(`./fixtures/${name}`)).arrayBuffer());
  const ok = decoded.length === original.length &&
    (await sha256Hex(decoded)) === (await sha256Hex(original));

  results.push({ name, served: frame.length, original: original.length, ms, ok, decoded });

  const row = document.createElement('tr');
  row.innerHTML = `<td>${name}</td><td>${frame.length.toLocaleString()}</td>` +
    `<td>${original.length.toLocaleString()}</td>` +
    `<td>${(100 - (100 * frame.length) / original.length).toFixed(1)}%</td>` +
    `<td>${ms.toFixed(3)}</td>` +
    `<td>${(original.length / ms / 1000).toFixed(1)}</td>` +
    `<td class="${ok ? 'ok' : 'bad'}">${ok ? 'byte-exact' : 'MISMATCH'}</td>`;
  tbody.appendChild(row);
}

// Use the decoded bytes for real, not just measure them.
const css = results.find((r) => r.name.endsWith('.css'));
if (css?.ok) {
  const sheet = new CSSStyleSheet();
  await sheet.replace(new TextDecoder().decode(css.decoded) +
    '\n.decoded-css-target{padding:.6rem;border-left:3px solid currentColor}');
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
}
const json = results.find((r) => r.name.endsWith('.json'));
let parsedNote = '';
if (json?.ok) {
  const value = JSON.parse(new TextDecoder().decode(json.decoded));
  parsedNote = ` JSON parsed from decoded bytes: ${Array.isArray(value) ? value.length + ' entries' : Object.keys(value).length + ' keys'}.`;
}
const font = results.find((r) => r.name.endsWith('.woff2'));
let fontNote = '';
if (font?.ok) {
  try {
    const face = new FontFace('CubrimDecoded', font.decoded.buffer);
    await face.load();
    document.fonts.add(face);
    fontNote = ' Font face loaded from decoded bytes.';
  } catch (err) {
    fontNote = ` Font load failed: ${err.message}`;
  }
}
document.getElementById('applied-note').textContent =
  'Stylesheet applied from decoded bytes.' + parsedNote + fontNote;

const totalOriginal = results.reduce((a, r) => a + r.original, 0);
const totalServed = results.reduce((a, r) => a + r.served, 0);
const totalMs = results.reduce((a, r) => a + r.ms, 0);
const allOk = results.every((r) => r.ok);
summary.textContent =
  `${results.length} assets · served ${totalServed.toLocaleString()} B for ` +
  `${totalOriginal.toLocaleString()} B of content ` +
  `(${(100 - (100 * totalServed) / totalOriginal).toFixed(1)}% less traffic) · ` +
  `decoded in ${totalMs.toFixed(2)} ms · ` +
  `${(totalOriginal / totalMs / 1000).toFixed(1)} MB/s · ` +
  (allOk ? 'every asset byte-exact' : 'A MISMATCH WAS FOUND');

// Handshake for the headless harness: it waits for this, then reads the JSON.
window.__cubrimResults = {
  assets: results.map(({ name, served, original, ms, ok }) => ({ name, served, original, ms, ok })),
  totalOriginal, totalServed, totalMs, allOk,
  userAgent: navigator.userAgent,
  memory: performance.memory ? performance.memory.usedJSHeapSize : null,
  wasmHeapBytes: cubrim.memory.buffer.byteLength,
  repeats: 25,
  warmups: 3,
  timerNote: 'per-decode time is a 25-iteration loop divided by 25, to amortise browser timer coarsening',
};
document.title = allOk ? 'cubrim-demo-ok' : 'cubrim-demo-mismatch';

// Machine-readable copy, so a headless run can read the numbers out of the DOM
// without a DevTools session.
const dump = document.createElement('pre');
dump.id = 'cubrim-json';
dump.textContent = JSON.stringify(window.__cubrimResults);
document.body.appendChild(dump);

// Report to the harness. connect-src 'self' permits exactly this and nothing
// off-origin.
try {
  await fetch('/__results', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(window.__cubrimResults),
  });
} catch (err) {
  console.error('result POST failed', err);
}
