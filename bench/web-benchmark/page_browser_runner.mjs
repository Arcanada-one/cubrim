#!/usr/bin/env node

// Drive the explicit-WASM page fixture with the system Chromium binary.
// The page posts its measurements to the real Cubrim demo server; this helper
// only controls the browser lifetime and returns the page-owned result.

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { unlink } from 'node:fs/promises';
import { setTimeout as delay } from 'node:timers/promises';
import { createDemoServer } from '../../code/cubrim-web-decoder/web/serve.mjs';

const [root, browser = '/snap/bin/chromium', trialsText = '30', warmupsText = '3'] = process.argv.slice(2);
if (!root) {
  console.error('usage: page_browser_runner.mjs <fixture-root> [browser] [trials] [warmups]');
  process.exit(2);
}

const trials = Number(trialsText);
const warmups = Number(warmupsText);
if (!Number.isInteger(trials) || trials < 30 || !Number.isInteger(warmups) || warmups !== 3) {
  throw new Error('explicit page protocol requires at least 30 trials and exactly 3 warmups');
}
if (!existsSync(browser)) throw new Error(`browser is not a regular configured path: ${browser}`);

const resultPath = `${root}/browser-results.json`;
const server = createDemoServer(root);
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
const address = server.address();
if (!address || typeof address === 'string') throw new Error('browser fixture server did not expose a TCP port');
const baseUrl = `http://127.0.0.1:${address.port}/`;

function terminate(child) {
  if (child.exitCode !== null) return;
  child.kill('SIGTERM');
  setTimeout(() => child.kill('SIGKILL'), 1000).unref();
}

async function waitForResult(timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(resultPath)) {
      const result = JSON.parse(await BunlessRead(resultPath));
      if (result && result.status === 'ok') return result;
      throw new Error(`page browser returned an error: ${JSON.stringify(result)}`);
    }
    await delay(50);
  }
  throw new Error('timed out waiting for page browser result');
}

// Keep this helper dependency-free: Node 22 has global fetch, but reading a
// local file through it is intentionally not supported.
async function BunlessRead(path) {
  const { readFile } = await import('node:fs/promises');
  return readFile(path, 'utf8');
}

async function runTrial(trialNo, warmupNo = null) {
  try {
    await unlink(resultPath);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const profile = `${root}/profile-${warmupNo === null ? `trial-${trialNo}` : `warmup-${warmupNo}`}`;
  const args = [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-cache',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-extensions',
    '--disable-sync',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    `${baseUrl}?trial=${warmupNo === null ? trialNo : `warmup-${warmupNo}`}`,
  ];
  const child = spawn(browser, args, { stdio: ['ignore', 'ignore', 'pipe'] });
  let stderr = '';
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  try {
    const result = await waitForResult();
    return { ...result, trial_no: warmupNo === null ? trialNo : -warmupNo };
  } catch (error) {
    const detail = stderr.trim().slice(-2000);
    throw new Error(`${error.message}${detail ? `; chromium: ${detail}` : ''}`);
  } finally {
    terminate(child);
    await delay(20);
  }
}

try {
  const results = [];
  for (let warmupNo = 1; warmupNo <= warmups; warmupNo += 1) {
    results.push(await runTrial(null, warmupNo));
  }
  for (let trialNo = 1; trialNo <= trials; trialNo += 1) {
    results.push(await runTrial(trialNo));
  }
  process.stdout.write(`${JSON.stringify({ browser: browser, results })}\n`);
} finally {
  await new Promise((resolve) => server.close(resolve));
}
