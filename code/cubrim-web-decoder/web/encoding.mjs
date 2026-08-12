// Content-Encoding negotiation for the `cbm` content coding (CUBR-0072).
//
// This is the epic's namesake mechanism: a client lists `cbm` in
// `Accept-Encoding`, the server answers with `Content-Encoding: cbm` and a
// Cubrim Web Profile frame as the response body. The frame bytes are exactly
// the ones `Content-Type: application/cubrim` serves; only the HTTP framing
// differs.
//
// Parsing follows RFC 9110 §12.5.3. Selection is deliberately narrower than
// the RFC allows in one place: `*` (a wildcard that formally matches any
// coding) never selects `cbm`. A generic client advertising `*` has no Cubrim
// decoder, and the canon rule for this epic is "pick Cubrim only for clients
// that support it" — so `cbm` is chosen only when the token itself appears
// with a non-zero weight. `*` still participates in excluding `identity`
// (`*;q=0`), where the RFC meaning is safe to honour.

/**
 * Parse an `Accept-Encoding` header value.
 *
 * Returns the codings in header order as `{ coding, q }`, with the coding
 * lowercased and `q` already resolved (missing weight = 1). Malformed members
 * — an empty element, a bad token, a q-value outside the RFC 9110 grammar —
 * are dropped rather than guessed at: an unparseable claim of support is not
 * a claim of support. Only the first occurrence of a coding is kept.
 *
 * @param {string} header
 * @returns {Array<{coding: string, q: number}>}
 */
export function parseAcceptEncoding(header) {
  const TOKEN = /^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/;
  const QVALUE = /^(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$/;

  const seen = new Set();
  const entries = [];
  for (const rawMember of String(header).split(',')) {
    const [rawCoding, ...rawParams] = rawMember.split(';');
    const coding = rawCoding.trim().toLowerCase();
    if (!(coding === '*' || TOKEN.test(coding))) continue;

    let q = 1;
    let malformed = false;
    for (const rawParam of rawParams) {
      const eq = rawParam.indexOf('=');
      if (eq === -1) {
        malformed = true;
        break;
      }
      const name = rawParam.slice(0, eq).trim().toLowerCase();
      const value = rawParam.slice(eq + 1).trim();
      if (name !== 'q') continue; // unknown parameters are ignored, per RFC
      if (!QVALUE.test(value)) {
        malformed = true;
        break;
      }
      q = Number(value);
    }
    if (malformed || seen.has(coding)) continue;
    seen.add(coding);
    entries.push({ coding, q });
  }
  return entries;
}

/**
 * Choose the content coding for a response.
 *
 * @param {string|undefined} header the request's `Accept-Encoding` value;
 *   `undefined` when the header is absent
 * @param {string[]} available non-identity codings the server can produce for
 *   this resource, in server preference order (e.g. `['cbm']`)
 * @returns {string|null} the chosen coding, `'identity'` for an unencoded
 *   response, or `null` when the client forbade identity and nothing else is
 *   acceptable — the caller should answer 406
 */
export function negotiate(header, available) {
  // No header: the client states no preference. Serve identity — a client
  // that did not claim `cbm` cannot decode it.
  if (header === undefined || header === null) return 'identity';

  const entries = parseAcceptEncoding(header);
  const weight = new Map(entries.map(({ coding, q }) => [coding, q]));

  // Explicit tokens only — `*` never selects a coding here (see file header).
  let chosen = null;
  for (const coding of available) {
    const q = weight.get(coding);
    if (q !== undefined && q > 0 && (chosen === null || q > chosen.q)) {
      chosen = { coding, q };
    }
  }
  if (chosen !== null) return chosen.coding;

  // Identity is acceptable unless excluded explicitly or through `*;q=0`.
  const identityQ = weight.get('identity') ?? weight.get('*') ?? 1;
  return identityQ > 0 ? 'identity' : null;
}
