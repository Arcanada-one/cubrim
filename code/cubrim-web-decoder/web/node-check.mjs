// Validate the WASM module in a real engine outside the browser.
//
// Node's WebAssembly is the same V8 engine the browser demo runs on, so this
// catches ABI and glue faults without a display; the browser run is still what
// satisfies CUBR-0077's AC-1 and is reported separately.
//
// Usage: node node-check.mjs <wasm-path> <fixture-dir>

import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { CubrimDecoder } from './cubrim.js';

const [, , wasmPath, fixtureDir] = process.argv;
if (!wasmPath || !fixtureDir) {
  console.error('usage: node node-check.mjs <wasm-path> <fixture-dir>');
  process.exit(2);
}

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');

const module = await readFile(wasmPath);
const cubrim = await CubrimDecoder.load(new Uint8Array(module));

const names = (await readdir(fixtureDir))
  .filter((n) => n.endsWith('.cbr'))
  .map((n) => n.slice(0, -4))
  .sort();

let failures = 0;
let totalOriginal = 0;
let totalServed = 0;
let totalMs = 0;

console.log(`# wasm ${wasmPath} (${module.length} bytes) | node ${process.version}`);
console.log(
  ['asset', 'served', 'original', 'decode_ms', 'MB_s', 'check'].join('\t'),
);

for (const name of names) {
  const frame = new Uint8Array(await readFile(`${fixtureDir}/${name}.cbr`));
  const original = new Uint8Array(await readFile(`${fixtureDir}/${name}`));

  // Warm the engine, then take the best of several timed decodes.
  for (let i = 0; i < 3; i += 1) cubrim.cubrimDecode(frame, 64 << 20);
  let best = Infinity;
  let decoded;
  for (let i = 0; i < 20; i += 1) {
    const t0 = process.hrtime.bigint();
    decoded = cubrim.cubrimDecode(frame, 64 << 20);
    const ms = Number(process.hrtime.bigint() - t0) / 1e6;
    if (ms < best) best = ms;
  }

  const ok = decoded.length === original.length &&
    sha256(Buffer.from(decoded)) === sha256(Buffer.from(original));
  if (!ok) failures += 1;

  totalOriginal += original.length;
  totalServed += frame.length;
  totalMs += best;
  console.log(
    [
      name,
      frame.length,
      original.length,
      best.toFixed(3),
      (original.length / best / 1000).toFixed(1),
      ok ? 'byte-exact' : 'MISMATCH',
    ].join('\t'),
  );
}

// Hostile input must be rejected, not crash the module or the page.
const hostile = [
  new Uint8Array(0),
  new Uint8Array([1, 2, 3]),
  new Uint8Array(64),
  (() => {
    const f = new Uint8Array(64);
    f.set([0xcb, 0x52, 0x49, 0x4d, 1, 18], 0);
    f.set([0xff, 0xff, 0xff, 0xff], 6); // absurd declared length
    return f;
  })(),
];
let rejected = 0;
for (const frame of hostile) {
  try {
    cubrim.cubrimDecode(frame, 1 << 20);
    console.log(`HOSTILE ACCEPTED (${frame.length} bytes) — that is a failure`);
    failures += 1;
  } catch {
    rejected += 1;
  }
}

console.log(
  `AGGREGATE served=${totalServed} original=${totalOriginal} ` +
    `traffic_reduction=${(100 - (100 * totalServed) / totalOriginal).toFixed(2)}% ` +
    `decode_ms=${totalMs.toFixed(3)} MB_s=${(totalOriginal / totalMs / 1000).toFixed(1)} ` +
    `hostile_rejected=${rejected}/${hostile.length} failures=${failures}`,
);
process.exit(failures === 0 ? 0 : 1);
