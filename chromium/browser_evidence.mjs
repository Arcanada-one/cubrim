#!/usr/bin/env node
// CUBR-0079 P4: prove the browser received decoded bytes, then capture the
// rendered page. The browser fetches the same negotiated URL, so the
// ArrayBuffer is produced after Chromium's Content-Encoding filter ran.

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

const [portText, doc, originPath, screenshotPath] = process.argv.slice(2);
const port = Number(portText);

if (!Number.isInteger(port) || !doc || !originPath || !screenshotPath) {
  console.error(
    `usage: ${process.argv[1]} PORT DOC ORIGIN_PATH SCREENSHOT_PATH`,
  );
  process.exit(2);
}

const baseUrl = `http://127.0.0.1:${port}`;
const deadline = Date.now() + 30_000;

const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

async function findPage() {
  const response = await fetch(`${baseUrl}/json/list`);
  if (!response.ok) throw new Error(`DevTools list returned ${response.status}`);
  const targets = await response.json();
  return targets.find(
    (target) => target.type === 'page' && target.url.includes(`/${doc}`),
  );
}

async function waitForPage() {
  while (Date.now() < deadline) {
    try {
      const target = await findPage();
      if (target?.webSocketDebuggerUrl) return target;
    } catch {
      // content_shell is still starting its DevTools endpoint.
    }
    await sleep(250);
  }
  throw new Error(`no DevTools page target for /${doc}`);
}

function connect(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  const pending = new Map();
  let nextId = 1;

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id);
    pending.delete(message.id);
    clearTimeout(request.timer);
    if (message.error) {
      request.reject(new Error(JSON.stringify(message.error)));
    } else {
      request.resolve(message.result);
    }
  });

  socket.addEventListener('close', () => {
    for (const request of pending.values()) {
      clearTimeout(request.timer);
      request.reject(new Error('DevTools WebSocket closed'));
    }
    pending.clear();
  });

  const call = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`DevTools call timed out: ${method}`));
      }, 15_000);
      pending.set(id, { resolve, reject, timer });
      socket.send(JSON.stringify({ id, method, params }));
    });

  return {
    socket,
    open: new Promise((resolve, reject) => {
      socket.addEventListener('open', resolve, { once: true });
      socket.addEventListener('error', reject, { once: true });
    }),
    call,
  };
}

const decodedBodyExpression = `(() => {
  const hex = (bytes) => [...new Uint8Array(bytes)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return fetch(location.href, { cache: 'no-store' }).then(async (response) => {
    const body = await response.arrayBuffer();
    const sha256 = await crypto.subtle.digest('SHA-256', body);
    return {
      status: response.status,
      url: response.url,
      byteLength: body.byteLength,
      sha256: hex(sha256),
      readyState: document.readyState,
    };
  });
})()`;

async function main() {
  const target = await waitForPage();
  const devtools = connect(target.webSocketDebuggerUrl);
  await devtools.open;

  const evaluated = await devtools.call('Runtime.evaluate', {
    expression: decodedBodyExpression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (evaluated.exceptionDetails) {
    throw new Error(JSON.stringify(evaluated.exceptionDetails));
  }
  const browserBody = evaluated.result?.value;
  if (!browserBody || typeof browserBody.sha256 !== 'string') {
    throw new Error('browser did not return decoded-body evidence');
  }

  const screenshot = await devtools.call('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
  });
  const screenshotBytes = Buffer.from(screenshot.data, 'base64');
  writeFileSync(screenshotPath, screenshotBytes, { mode: 0o600 });

  const originBytes = readFileSync(originPath);
  const originSha256 = createHash('sha256').update(originBytes).digest('hex');
  const bodyMatches =
    browserBody.status === 200 &&
    browserBody.byteLength === originBytes.length &&
    browserBody.sha256 === originSha256;
  const screenshotSha256 = createHash('sha256')
    .update(screenshotBytes)
    .digest('hex');

  console.log(`  browser fetch status             : ${browserBody.status}`);
  console.log(`  browser decoded body bytes      : ${browserBody.byteLength}`);
  console.log(`  origin body bytes               : ${originBytes.length}`);
  console.log(`  browser decoded body SHA-256    : ${browserBody.sha256}`);
  console.log(`  origin body SHA-256             : ${originSha256}`);
  console.log(`  decoded body matches origin     : ${bodyMatches}`);
  console.log(`  rendered screenshot bytes       : ${screenshotBytes.length}`);
  console.log(`  rendered screenshot SHA-256     : ${screenshotSha256}`);
  console.log(`  rendered document readyState    : ${browserBody.readyState}`);

  devtools.socket.close();
  if (!bodyMatches || screenshotBytes.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(`browser evidence failed: ${error.message}`);
  process.exitCode = 1;
});
