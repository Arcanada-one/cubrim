#!/usr/bin/env node
// CUBR-0072: collect page timing from a real Content-Encoding: cbm browser
// navigation. The browser is navigated only after the observers are installed
// through DevTools, so the metrics belong to the initial document response.

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

import { calculatePageMetrics } from './page_metrics.mjs';

const [portText, pageUrl, doc, originPath, screenshotPath, outputPath] =
  process.argv.slice(2);
const port = Number(portText);

if (
  !Number.isInteger(port) ||
  !pageUrl ||
  !doc ||
  !originPath ||
  !screenshotPath ||
  !outputPath
) {
  console.error(
    `usage: ${process.argv[1]} PORT PAGE_URL DOC ORIGIN_PATH SCREENSHOT_PATH OUTPUT_JSON`,
  );
  process.exit(2);
}

const baseUrl = `http://127.0.0.1:${port}`;
const deadline = Date.now() + 45_000;

const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

async function findPage() {
  const response = await fetch(`${baseUrl}/json/list`);
  if (!response.ok) throw new Error(`DevTools list returned ${response.status}`);
  const targets = await response.json();
  return targets.find((target) => target.type === 'page');
}

async function waitForPage() {
  while (Date.now() < deadline) {
    try {
      const target = await findPage();
      if (target?.webSocketDebuggerUrl) return target;
    } catch {
      // content_shell is still starting its DevTools endpoint.
    }
    await sleep(100);
  }
  throw new Error('no DevTools page target');
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
    if (message.error) request.reject(new Error(JSON.stringify(message.error)));
    else request.resolve(message.result);
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

const installObservers = `(() => {
  const state = { longTasks: [], lcpEntries: [] };
  window.__cubrTransparentPageMetrics = state;
  try {
    new PerformanceObserver((list) => state.longTasks.push(...list.getEntries()))
      .observe({ type: 'longtask', buffered: true });
  } catch {}
  try {
    new PerformanceObserver((list) => state.lcpEntries.push(...list.getEntries()))
      .observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {}
})()`;

const timingExpression = `(() => {
  const navigation = performance.getEntriesByType('navigation')[0];
  const state = window.__cubrTransparentPageMetrics || {};
  return {
    navigation: navigation && {
      responseStart: navigation.responseStart,
      loadEventEnd: navigation.loadEventEnd,
    },
    paintEntries: performance.getEntriesByType('paint').map((entry) => ({
      name: entry.name,
      startTime: entry.startTime,
    })),
    lcpEntries: (state.lcpEntries || []).map((entry) => ({
      startTime: entry.startTime,
    })),
    longTaskEntries: (state.longTasks || []).map((entry) => ({
      duration: entry.duration,
    })),
    now: performance.now(),
  };
})()`;

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

async function waitForDocument(devtools) {
  while (Date.now() < deadline) {
    try {
      const evaluated = await devtools.call('Runtime.evaluate', {
        expression: '({href: location.href, readyState: document.readyState})',
        returnByValue: true,
      });
      const page = evaluated.result?.value;
      if (page?.href === pageUrl && page.readyState === 'complete') return page;
    } catch {
      // The navigation context may not have committed yet.
    }
    await sleep(100);
  }
  throw new Error(`document execution context did not commit ${pageUrl}`);
}

async function main() {
  const target = await waitForPage();
  const devtools = connect(target.webSocketDebuggerUrl);
  try {
    await devtools.open;
    await devtools.call('Page.enable');
    await devtools.call('Runtime.enable');
    await devtools.call('Page.addScriptToEvaluateOnNewDocument', {
      source: installObservers,
    });
    await devtools.call('Page.navigate', { url: pageUrl });
    const page = await waitForDocument(devtools);
    await devtools.call('Runtime.evaluate', {
      expression:
        'new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 100))))',
      awaitPromise: true,
    });

    const timing = await devtools.call('Runtime.evaluate', {
      expression: timingExpression,
      returnByValue: true,
    });
    if (timing.exceptionDetails) throw new Error(JSON.stringify(timing.exceptionDetails));
    const timingValue = timing.result?.value;
    const metrics = calculatePageMetrics(timingValue);

    const evaluated = await devtools.call('Runtime.evaluate', {
      expression: decodedBodyExpression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (evaluated.exceptionDetails) throw new Error(JSON.stringify(evaluated.exceptionDetails));
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
    if (!bodyMatches || screenshotBytes.length === 0) {
      throw new Error('decoded body or screenshot proof failed');
    }

    const row = {
      schema_version: 1,
      page_url: pageUrl,
      document: doc,
      page: {
        href: page.href,
        ready_state: browserBody.readyState,
      },
      body: {
        status: browserBody.status,
        byte_length: browserBody.byteLength,
        sha256: browserBody.sha256,
        origin_byte_length: originBytes.length,
        origin_sha256: originSha256,
        roundtrip_exact: true,
      },
      screenshot: {
        byte_length: screenshotBytes.length,
        sha256: createHash('sha256').update(screenshotBytes).digest('hex'),
      },
      metrics,
    };
    writeFileSync(outputPath, `${JSON.stringify(row, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(row));
  } finally {
    devtools.socket.close();
  }
}

main().catch((error) => {
  console.error(`transparent page evidence failed: ${error.message}`);
  process.exitCode = 1;
});
