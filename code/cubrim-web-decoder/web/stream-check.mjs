// Verify the streaming API through the real WASM module, against real fixtures.
//
// Usage: node stream-check.mjs <wasm-path> <fixture-dir>

import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { CubrimDecoder } from './cubrim.js';

const [, , wasmPath, fixtureDir] = process.argv;
if (!wasmPath || !fixtureDir) {
  console.error('usage: node stream-check.mjs <wasm-path> <fixture-dir>');
  process.exit(2);
}

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
const cubrim = await CubrimDecoder.load(new Uint8Array(await readFile(wasmPath)));

const names = (await readdir(fixtureDir))
  .filter((n) => n.endsWith('.cbr'))
  .map((n) => n.slice(0, -4))
  .sort();

let failures = 0;
console.log(['asset', 'chunk', 'yields', 'progressive', 'check'].join('\t'));

for (const name of names) {
  const frame = new Uint8Array(await readFile(`${fixtureDir}/${name}.cbr`));
  const original = new Uint8Array(await readFile(`${fixtureDir}/${name}`));

  for (const chunkSize of [1024, 4096]) {
    // Feed it the way a network would: a sequence of arbitrary-sized chunks.
    async function* pieces() {
      for (let i = 0; i < frame.length; i += chunkSize) {
        yield frame.subarray(i, Math.min(i + chunkSize, frame.length));
      }
    }

    const collected = [];
    let yields = 0;
    let progressiveAt = -1;
    const generator = cubrim.cubrimDecodeStream(pieces(), 64 << 20);
    let result = await generator.next();
    while (!result.done) {
      collected.push(result.value);
      yields += 1;
      if (progressiveAt < 0) progressiveAt = collected.reduce((a, c) => a + c.length, 0);
      result = await generator.next();
    }
    const whole = result.value;

    const joined = new Uint8Array(collected.reduce((a, c) => a + c.length, 0));
    let at = 0;
    for (const piece of collected) {
      joined.set(piece, at);
      at += piece.length;
    }

    const ok =
      sha256(Buffer.from(whole)) === sha256(Buffer.from(original)) &&
      sha256(Buffer.from(joined)) === sha256(Buffer.from(original));
    if (!ok) failures += 1;

    console.log(
      [
        name,
        chunkSize,
        yields,
        yields > 1 ? `yes (first ${progressiveAt}B)` : 'no (single block)',
        ok ? 'byte-exact' : 'MISMATCH',
      ].join('\t'),
    );
  }
}

// A corrupted frame must reject at finish, not silently deliver.
{
  const name = names[0];
  const frame = new Uint8Array(await readFile(`${fixtureDir}/${name}.cbr`));
  if (frame[5] === 18) {
    const corrupt = Uint8Array.from(frame);
    corrupt[13] ^= 0xff; // checksum byte
    let threw = false;
    try {
      const generator = cubrim.cubrimDecodeStream([corrupt], 64 << 20);
      for (;;) {
        const step = await generator.next();
        if (step.done) break;
      }
    } catch {
      threw = true;
    }
    console.log(`corrupt-checksum\t-\t-\t-\t${threw ? 'rejected' : 'ACCEPTED (failure)'}`);
    if (!threw) failures += 1;
  }
}

console.log(`failures=${failures}`);
process.exit(failures === 0 ? 0 : 1);
