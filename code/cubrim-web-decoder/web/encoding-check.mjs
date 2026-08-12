// Content-Encoding: cbm, end to end (CUBR-0072).
//
// Two layers, both against the real artefacts rather than mocks:
//
//   1. the negotiation functions in `encoding.mjs` — RFC 9110 parsing and the
//      deliberately conservative selection rule;
//   2. the demo server from `serve.mjs` on an ephemeral port, with responses
//      decoded through the real WASM module — including a streaming decode
//      straight from a `fetch` response body, which is the shape a browser
//      integration would use.
//
// Usage: node encoding-check.mjs <wasm-path> <fixture-dir> <blocked-fixture-dir>
//
// `<fixture-dir>` holds single-block fixtures (original + `<name>.cbr`);
// `<blocked-fixture-dir>` holds the same assets cut into multi-block frames,
// which is what makes progressive output over HTTP observable.

import { readFile, readdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { request } from 'node:http';
import { join } from 'node:path';
import { CubrimDecoder } from './cubrim.js';
import { parseAcceptEncoding, negotiate } from './encoding.mjs';
import { createDemoServer } from './serve.mjs';

const [, , wasmPath, fixtureDir, blockedDir] = process.argv;
if (!wasmPath || !fixtureDir || !blockedDir) {
  console.error('usage: node encoding-check.mjs <wasm-path> <fixture-dir> <blocked-fixture-dir>');
  process.exit(2);
}

let checks = 0;
let failures = 0;
function check(name, cond) {
  checks += 1;
  if (!cond) {
    failures += 1;
    console.error(`FAIL ${name}`);
  }
}

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');

// --- layer 1: negotiation ---------------------------------------------------

check(
  'parse: plain list',
  JSON.stringify(parseAcceptEncoding('cbm, br, gzip')) ===
    JSON.stringify([
      { coding: 'cbm', q: 1 },
      { coding: 'br', q: 1 },
      { coding: 'gzip', q: 1 },
    ]),
);
check(
  'parse: weights and case',
  JSON.stringify(parseAcceptEncoding('CBM;q=0.5, GZIP ; q=0.08')) ===
    JSON.stringify([
      { coding: 'cbm', q: 0.5 },
      { coding: 'gzip', q: 0.08 },
    ]),
);
check('parse: q above 1 drops the member', parseAcceptEncoding('cbm;q=2').length === 0);
check('parse: q with 4 decimals drops the member', parseAcceptEncoding('cbm;q=0.5001').length === 0);
check('parse: bare q= drops the member', parseAcceptEncoding('cbm;q').length === 0);
check('parse: empty member dropped', parseAcceptEncoding(' , cbm').length === 1);
check('parse: non-token dropped', parseAcceptEncoding('cb m, gzip').length === 1);
check(
  'parse: unknown parameter ignored',
  JSON.stringify(parseAcceptEncoding('cbm;level=9;q=0.5')) ===
    JSON.stringify([{ coding: 'cbm', q: 0.5 }]),
);
check(
  'parse: first occurrence wins',
  JSON.stringify(parseAcceptEncoding('cbm;q=0, cbm')) ===
    JSON.stringify([{ coding: 'cbm', q: 0 }]),
);

check('negotiate: absent header -> identity', negotiate(undefined, ['cbm']) === 'identity');
check('negotiate: empty header -> identity', negotiate('', ['cbm']) === 'identity');
check('negotiate: cbm listed -> cbm', negotiate('cbm, br, gzip', ['cbm']) === 'cbm');
check('negotiate: cbm case-insensitive', negotiate('CBM', ['cbm']) === 'cbm');
check('negotiate: cbm absent -> identity', negotiate('gzip, br', ['cbm']) === 'identity');
check('negotiate: cbm;q=0 -> identity', negotiate('cbm;q=0', ['cbm']) === 'identity');
check('negotiate: low weight still selects', negotiate('cbm;q=0.1, gzip', ['cbm']) === 'cbm');
check('negotiate: wildcard never selects cbm', negotiate('*', ['cbm']) === 'identity');
check('negotiate: identity forbidden, no cbm -> 406', negotiate('identity;q=0', ['cbm']) === null);
check('negotiate: identity forbidden but cbm listed', negotiate('identity;q=0, cbm', ['cbm']) === 'cbm');
check('negotiate: *;q=0 forbids identity', negotiate('*;q=0', ['cbm']) === null);
check('negotiate: *;q=0 with explicit identity', negotiate('*;q=0, identity', ['cbm']) === 'identity');
check('negotiate: malformed cbm claim not honoured', negotiate('cbm;q=broken', ['cbm']) === 'identity');

// --- layer 2: the real server, the real module ------------------------------

const cubrim = await CubrimDecoder.load(new Uint8Array(await readFile(wasmPath)));

// A resource with no precompressed variant, to pin the untouched path.
await writeFile(join(fixtureDir, 'no-variant.txt'), 'no variant here\n');

function get(port, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = request(
      { host: '127.0.0.1', port, path, headers },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () =>
          resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }),
        );
      },
    );
    req.on('error', reject);
    req.end();
  });
}

async function withServer(root, fn) {
  const server = createDemoServer(root);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    await fn(server.address().port);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

const names = (await readdir(fixtureDir))
  .filter((n) => n.endsWith('.cbr'))
  .map((n) => n.slice(0, -4))
  .sort();
check('fixtures present', names.length >= 12);

await withServer(fixtureDir, async (port) => {
  // Every census asset: negotiated cbm response decodes byte-exactly.
  for (const name of names) {
    const original = await readFile(join(fixtureDir, name));
    const frame = await readFile(join(fixtureDir, `${name}.cbr`));
    const res = await get(port, `/${name}`, { 'accept-encoding': 'cbm, br, gzip' });
    check(`${name}: 200`, res.status === 200);
    check(`${name}: content-encoding cbm`, res.headers['content-encoding'] === 'cbm');
    check(`${name}: vary accept-encoding`, res.headers.vary === 'Accept-Encoding');
    check(`${name}: content-type is the resource's`, res.headers['content-type'] !== 'application/cubrim');
    check(`${name}: body is the frame`, res.body.equals(frame));
    check(
      `${name}: declared length matches`,
      Number(res.headers['content-length']) === frame.length,
    );
    const decoded = cubrim.cubrimDecode(new Uint8Array(res.body), 64 << 20);
    check(`${name}: decodes byte-exact`, sha256(Buffer.from(decoded)) === sha256(original));
  }

  const name = names[0];
  const original = await readFile(join(fixtureDir, name));
  const frame = await readFile(join(fixtureDir, `${name}.cbr`));

  // A client that never mentioned cbm gets identity — with Vary still set.
  for (const headers of [{}, { 'accept-encoding': 'gzip, deflate, br' }, { 'accept-encoding': 'cbm;q=0' }, { 'accept-encoding': '*' }]) {
    const res = await get(port, `/${name}`, headers);
    const label = headers['accept-encoding'] ?? '(absent)';
    check(`identity [${label}]: 200`, res.status === 200);
    check(`identity [${label}]: no content-encoding`, res.headers['content-encoding'] === undefined);
    check(`identity [${label}]: vary accept-encoding`, res.headers.vary === 'Accept-Encoding');
    check(`identity [${label}]: original bytes`, res.body.equals(original));
  }

  // Identity forbidden and cbm not claimed: 406, not a silent identity.
  const notAcceptable = await get(port, `/${name}`, { 'accept-encoding': 'identity;q=0' });
  check('406 when nothing acceptable', notAcceptable.status === 406);
  check('406 carries vary', notAcceptable.headers.vary === 'Accept-Encoding');

  // The application/cubrim transport is untouched by negotiation.
  const direct = await get(port, `/${name}.cbr`, { 'accept-encoding': 'cbm' });
  check('direct .cbr: application/cubrim', direct.headers['content-type'] === 'application/cubrim');
  check('direct .cbr: no content-encoding', direct.headers['content-encoding'] === undefined);
  check('direct .cbr: frame bytes', direct.body.equals(frame));

  // A resource with no variant negotiates nothing and varies on nothing.
  const plain = await get(port, '/no-variant.txt', { 'accept-encoding': 'cbm' });
  check('no variant: 200', plain.status === 200);
  check('no variant: no content-encoding', plain.headers['content-encoding'] === undefined);
  check('no variant: no vary', plain.headers.vary === undefined);
});

// Streaming decode of a negotiated response body, through fetch itself —
// multi-block fixtures so output is observable before the response ends.
const blockedNames = (await readdir(blockedDir))
  .filter((n) => n.endsWith('.cbr'))
  .map((n) => n.slice(0, -4))
  .sort();
check('blocked fixtures present', blockedNames.length >= 12);

// How many chunks a body arrives in is the network's choice, not the codec's —
// on loopback these bodies routinely arrive whole, so per-block progressive
// output is NOT asserted here. That property is stream-check.mjs's subject,
// which feeds the decoder controlled chunks. This layer asserts the transport
// contract: a negotiated response body pipes into the streaming decoder as-is
// and comes out byte-exact.
let progressive = 0;
await withServer(blockedDir, async (port) => {
  for (const name of blockedNames) {
    const original = await readFile(join(blockedDir, name));
    const res = await fetch(`http://127.0.0.1:${port}/${name}`, {
      headers: { 'accept-encoding': 'cbm' },
    });
    check(`${name}: stream 200`, res.status === 200);
    check(`${name}: stream content-encoding cbm`, res.headers.get('content-encoding') === 'cbm');
    const generator = cubrim.cubrimDecodeStream(res.body, 64 << 20);
    let yields = 0;
    let step = await generator.next();
    while (!step.done) {
      yields += 1;
      step = await generator.next();
    }
    if (yields > 1) progressive += 1;
    check(
      `${name}: streamed byte-exact`,
      sha256(Buffer.from(step.value)) === sha256(original),
    );
  }
});
console.log(`streaming: ${progressive}/${blockedNames.length} assets yielded progressively (informational)`);

console.log(`encoding-check: ${checks} checks, ${failures} failures`);
process.exit(failures === 0 ? 0 : 1);
