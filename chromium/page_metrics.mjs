// Browser-owned page timing extraction for the transparent HTTP proof.

const REQUIRED_METRICS = [
  'time_to_first_byte',
  'first_contentful_paint',
  'largest_contentful_paint',
  'total_blocking_time',
  'page_load_duration',
];

function requireMetric(value, name) {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${name} metric is not finite`);
  }
  return value;
}

function requireEntry(entries, predicate, name) {
  const entry = entries.find(predicate);
  if (!entry || !Number.isFinite(entry.startTime) || entry.startTime < 0) {
    throw new Error(`${name} entry is missing`);
  }
  return entry;
}

export function calculatePageMetrics({
  navigation,
  paintEntries,
  lcpEntries,
  longTaskEntries,
  now,
}) {
  if (!navigation) throw new Error('navigation entry is missing');
  const paint = requireEntry(
    paintEntries,
    (entry) => entry.name === 'first-contentful-paint',
    'first_contentful_paint',
  );
  const lcp = [...lcpEntries]
    .filter((entry) => Number.isFinite(entry.startTime) && entry.startTime >= 0)
    .at(-1);
  if (!lcp) throw new Error('largest_contentful_paint entry is missing');

  const totalBlockingTime = longTaskEntries.reduce(
    (sum, entry) =>
      sum +
      (Number.isFinite(entry.duration) && entry.duration > 50
        ? entry.duration - 50
        : 0),
    0,
  );
  const metrics = {
    time_to_first_byte: requireMetric(
      navigation.responseStart,
      'time_to_first_byte',
    ),
    first_contentful_paint: requireMetric(
      paint.startTime,
      'first_contentful_paint',
    ),
    largest_contentful_paint: requireMetric(
      lcp.startTime,
      'largest_contentful_paint',
    ),
    total_blocking_time: requireMetric(
      totalBlockingTime,
      'total_blocking_time',
    ),
    page_load_duration: requireMetric(
      Math.max(now, navigation.loadEventEnd || 0),
      'page_load_duration',
    ),
  };

  if (Object.keys(metrics).some((name) => !REQUIRED_METRICS.includes(name))) {
    throw new Error('unexpected page metric set');
  }
  return metrics;
}

export { REQUIRED_METRICS };
