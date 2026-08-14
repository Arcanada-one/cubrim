import test from 'node:test';
import assert from 'node:assert/strict';

import { calculatePageMetrics } from './page_metrics.mjs';

test('calculates the five page metrics from browser-owned entries', () => {
  const metrics = calculatePageMetrics({
    navigation: { responseStart: 12.5, loadEventEnd: 98 },
    paintEntries: [{ name: 'first-paint', startTime: 20 }, { name: 'first-contentful-paint', startTime: 31 }],
    lcpEntries: [{ startTime: 42 }, { startTime: 57 }],
    longTaskEntries: [{ duration: 48 }, { duration: 80 }, { duration: 55 }],
    now: 100,
  });

  assert.deepEqual(metrics, {
    time_to_first_byte: 12.5,
    first_contentful_paint: 31,
    largest_contentful_paint: 57,
    total_blocking_time: 35,
    page_load_duration: 100,
  });
});

test('fails closed when a required paint entry is missing', () => {
  assert.throws(
    () =>
      calculatePageMetrics({
        navigation: { responseStart: 12.5, loadEventEnd: 98 },
        paintEntries: [{ name: 'first-paint', startTime: 20 }],
        lcpEntries: [{ startTime: 57 }],
        longTaskEntries: [],
        now: 100,
      }),
    /first_contentful_paint entry is missing/,
  );
});
