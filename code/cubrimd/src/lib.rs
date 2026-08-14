//! cubrimd — a reverse proxy that speaks `Content-Encoding: cbm` (CUBR-0078).
//!
//! Canon stage 3: the fastest server-side route for the web codec is a
//! standalone proxy in front of the origin, not an nginx module. The proxy
//! owns exactly one content coding:
//!
//! * a client that lists `cbm` in `Accept-Encoding` gets eligible responses
//!   compressed with the Cubrim Web Profile and labelled
//!   `Content-Encoding: cbm`;
//! * every other client's request is forwarded with the `cbm` token stripped,
//!   and whatever the origin negotiates instead — brotli, zstd, gzip,
//!   identity — passes through byte-untouched. That IS the fallback story:
//!   the origin already speaks the incumbent codings, and re-implementing
//!   them here would only add a second place for them to be wrong.
//!
//! Every response whose representation depends on `Accept-Encoding` at this
//! hop carries `Vary: Accept-Encoding`, whichever representation is sent —
//! without it a shared cache would hand `cbm` bytes to a client that never
//! asked for them (the canon calls this out as the critical header).
//!
//! Selection policy matches the reference server in
//! `code/cubrim-web-decoder/web/encoding.mjs`: RFC 9110 §12.5.3 parsing, and
//! `cbm` is chosen only on an explicit token with non-zero weight — `*` never
//! selects it, because a generic client advertising `*` has no Cubrim decoder.
//!
//! Deliberately NOT here, stated rather than implied: TLS (run it behind the
//! terminator), HTTP/2 (the PoC transport is HTTP/1.1), request smuggling
//! hardening beyond hop-by-hop stripping, and any second content coding.

use std::collections::HashMap;
use std::collections::VecDeque;
use std::io::Read;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use cubrim::encode_web_dynamic;
use tiny_http::{Header, Method, Response, Server};

pub mod origin;
use origin::OriginResponse;

/// The content-coding token. A working name — IANA registration is a
/// hard-gated CUBR-0080 step, and nothing here presumes it happened.
pub const CODING: &str = "cbm";

/// Metrics endpoint path, namespaced so it cannot shadow an origin route by
/// accident (an origin that really serves this path can be put behind a
/// different prefix; the collision is documented, not silent).
pub const METRICS_PATH: &str = "/__cubrimd/metrics";

// ---------------------------------------------------------------------------
// Accept-Encoding negotiation (port of web/encoding.mjs, same semantics)
// ---------------------------------------------------------------------------

fn is_token(s: &str) -> bool {
    !s.is_empty()
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"!#$%&'*+.^_`|~-".contains(&b))
}

fn is_qvalue(s: &str) -> bool {
    let bytes = s.as_bytes();
    match bytes.first() {
        Some(b'0') | Some(b'1') => {}
        _ => return false,
    }
    if bytes.len() == 1 {
        return true;
    }
    if bytes.len() > 5 || bytes[1] != b'.' {
        return false;
    }
    let frac = &bytes[2..];
    if bytes[0] == b'1' {
        frac.iter().all(|&b| b == b'0')
    } else {
        frac.iter().all(|b| b.is_ascii_digit())
    }
}

/// Parse an `Accept-Encoding` value into `(coding, q)` pairs, header order,
/// codings lowercased, first occurrence winning. Malformed members are
/// dropped, not guessed at: an unparseable claim of support is not a claim
/// of support.
pub fn parse_accept_encoding(header: &str) -> Vec<(String, f64)> {
    let mut seen: Vec<(String, f64)> = Vec::new();
    'member: for member in header.split(',') {
        let mut parts = member.split(';');
        let coding = parts.next().unwrap_or("").trim().to_ascii_lowercase();
        if coding != "*" && !is_token(&coding) {
            continue;
        }
        let mut q = 1.0_f64;
        for param in parts {
            let Some((name, value)) = param.split_once('=') else {
                continue 'member;
            };
            if !name.trim().eq_ignore_ascii_case("q") {
                continue; // unknown parameters are ignored, per RFC
            }
            let value = value.trim();
            if !is_qvalue(value) {
                continue 'member;
            }
            q = value.parse().unwrap_or(0.0);
        }
        if seen.iter().any(|(c, _)| *c == coding) {
            continue;
        }
        seen.push((coding, q));
    }
    seen
}

/// Does this client claim the `cbm` coding? Explicit token with q > 0 only;
/// `*` never selects it (see module docs). Absent header = no claim.
pub fn wants_cbm(header: Option<&str>) -> bool {
    let Some(header) = header else { return false };
    parse_accept_encoding(header)
        .iter()
        .any(|(coding, q)| coding == CODING && *q > 0.0)
}

/// The client's `Accept-Encoding` as forwarded to the origin: the `cbm`
/// token removed (the origin does not speak it), everything else verbatim so
/// the origin's own negotiation — brotli, zstd, gzip — still happens.
pub fn strip_cbm(header: &str) -> String {
    header
        .split(',')
        .map(str::trim)
        .filter(|member| {
            let coding = member.split(';').next().unwrap_or("").trim();
            !coding.eq_ignore_ascii_case(CODING)
        })
        .collect::<Vec<_>>()
        .join(", ")
}

// ---------------------------------------------------------------------------
// Response eligibility
// ---------------------------------------------------------------------------

/// Content types worth offering to the encoder. The list is an allowlist:
/// already-compressed media (images, video, archives, most fonts) round-trips
/// through the no-regression rail as a raw-store frame, which costs header
/// bytes for nothing — so it is cheaper and honest to not negotiate at all.
pub fn compressible(content_type: &str) -> bool {
    let essence = content_type
        .split(';')
        .next()
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    essence.starts_with("text/")
        || essence.ends_with("+json")
        || essence.ends_with("+xml")
        || matches!(
            essence.as_str(),
            "application/json"
                | "application/javascript"
                | "application/x-javascript"
                | "application/xml"
                | "application/wasm"
                | "application/manifest+json"
                | "image/svg+xml"
        )
}

/// RFC 9110 §7.6.1 hop-by-hop headers, plus the ones this proxy recomputes.
fn skip_header(name: &str, when_compressing: bool) -> bool {
    let lower = name.to_ascii_lowercase();
    matches!(
        lower.as_str(),
        "connection"
            | "keep-alive"
            | "proxy-authenticate"
            | "proxy-authorization"
            | "te"
            | "trailer"
            | "transfer-encoding"
            | "upgrade"
            | "content-length"
    ) || (when_compressing && matches!(lower.as_str(), "content-encoding" | "vary" | "etag"))
}

/// Merge `Accept-Encoding` into an existing `Vary` value (or mint one).
fn merge_vary(existing: Option<&str>) -> String {
    match existing {
        None => "Accept-Encoding".to_owned(),
        Some(v)
            if v.split(',')
                .any(|m| m.trim().eq_ignore_ascii_case("accept-encoding") || m.trim() == "*") =>
        {
            v.to_owned()
        }
        Some(v) => format!("{v}, Accept-Encoding"),
    }
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

/// Counters, exposed as Prometheus text at [`METRICS_PATH`]. Saved-bytes are
/// tracked per real response rather than estimated: the canon's "real numbers
/// only" rule applies to operational metrics too.
#[derive(Default)]
pub struct Metrics {
    pub requests_total: AtomicU64,
    pub cbm_responses_total: AtomicU64,
    pub identity_eligible_total: AtomicU64,
    pub passthrough_total: AtomicU64,
    pub origin_errors_total: AtomicU64,
    pub cache_hits_total: AtomicU64,
    pub cache_misses_total: AtomicU64,
    pub original_bytes_total: AtomicU64,
    pub cbm_bytes_total: AtomicU64,
}

impl Metrics {
    pub fn render(&self) -> String {
        let g = |a: &AtomicU64| a.load(Ordering::Relaxed);
        format!(
            "# TYPE cubrimd_requests_total counter\n\
             cubrimd_requests_total {}\n\
             # TYPE cubrimd_cbm_responses_total counter\n\
             cubrimd_cbm_responses_total {}\n\
             # TYPE cubrimd_identity_eligible_total counter\n\
             cubrimd_identity_eligible_total {}\n\
             # TYPE cubrimd_passthrough_total counter\n\
             cubrimd_passthrough_total {}\n\
             # TYPE cubrimd_origin_errors_total counter\n\
             cubrimd_origin_errors_total {}\n\
             # TYPE cubrimd_cache_hits_total counter\n\
             cubrimd_cache_hits_total {}\n\
             # TYPE cubrimd_cache_misses_total counter\n\
             cubrimd_cache_misses_total {}\n\
             # TYPE cubrimd_original_bytes_total counter\n\
             cubrimd_original_bytes_total {}\n\
             # TYPE cubrimd_cbm_bytes_total counter\n\
             cubrimd_cbm_bytes_total {}\n",
            g(&self.requests_total),
            g(&self.cbm_responses_total),
            g(&self.identity_eligible_total),
            g(&self.passthrough_total),
            g(&self.origin_errors_total),
            g(&self.cache_hits_total),
            g(&self.cache_misses_total),
            g(&self.original_bytes_total),
            g(&self.cbm_bytes_total),
        )
    }
}

// ---------------------------------------------------------------------------
// Variant cache
// ---------------------------------------------------------------------------

/// FIFO-bounded cache of compressed variants, keyed by request path+query and
/// guarded by the origin's validator (`ETag`, else `Last-Modified`). A
/// response with no validator is never cached: serving a stale frame
/// byte-exactly is still serving the wrong representation.
struct VariantCache {
    map: HashMap<String, (String, Arc<Vec<u8>>)>,
    order: VecDeque<String>,
    max_entries: usize,
}

impl VariantCache {
    fn new(max_entries: usize) -> Self {
        Self {
            map: HashMap::new(),
            order: VecDeque::new(),
            max_entries,
        }
    }

    fn get(&self, key: &str, validator: &str) -> Option<Arc<Vec<u8>>> {
        self.map
            .get(key)
            .filter(|(v, _)| v == validator)
            .map(|(_, frame)| Arc::clone(frame))
    }

    fn insert(&mut self, key: String, validator: String, frame: Arc<Vec<u8>>) {
        if self.max_entries == 0 {
            return;
        }
        if !self.map.contains_key(&key) {
            self.order.push_back(key.clone());
            while self.order.len() > self.max_entries {
                if let Some(evicted) = self.order.pop_front() {
                    self.map.remove(&evicted);
                }
            }
        }
        self.map.insert(key, (validator, frame));
    }
}

// ---------------------------------------------------------------------------
// The proxy
// ---------------------------------------------------------------------------

pub struct Config {
    /// Origin base URL, e.g. `http://127.0.0.1:8080` (no trailing slash).
    pub origin: String,
    /// Cut frames into blocks of this size so streaming consumers make
    /// progress before the response ends. `None` = single-block.
    pub block_size: Option<usize>,
    /// Bodies above this are passed through unencoded: latency for the first
    /// byte of a huge dynamic response is worth more than its ratio.
    pub max_body_bytes: usize,
    /// Variant-cache capacity in entries (0 disables caching).
    pub cache_entries: usize,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            origin: String::new(),
            block_size: Some(65536),
            max_body_bytes: 8 << 20,
            cache_entries: 256,
        }
    }
}

pub struct Proxy {
    server: Server,
    state: Arc<State>,
}

struct State {
    config: Config,
    /// `host:port` of the origin, parsed once from `config.origin`.
    authority: String,
    metrics: Metrics,
    cache: Mutex<VariantCache>,
}

impl Proxy {
    /// Bind the listener. `listen` may use port 0; the bound port is
    /// available via [`Proxy::port`] before [`Proxy::run`] starts serving.
    pub fn bind(listen: &str, config: Config) -> Result<Self, String> {
        let authority = config
            .origin
            .strip_prefix("http://")
            .ok_or_else(|| format!("origin must be an http:// URL, got {}", config.origin))?
            .trim_end_matches('/')
            .to_owned();
        if authority.is_empty() || authority.contains('/') {
            return Err(format!(
                "origin must be http://host:port with no path, got {}",
                config.origin
            ));
        }
        let server = Server::http(listen).map_err(|e| format!("bind {listen}: {e}"))?;
        let cache = Mutex::new(VariantCache::new(config.cache_entries));
        Ok(Self {
            server,
            state: Arc::new(State {
                config,
                authority,
                metrics: Metrics::default(),
                cache,
            }),
        })
    }

    pub fn port(&self) -> u16 {
        self.server
            .server_addr()
            .to_ip()
            .map(|a| a.port())
            .unwrap_or(0)
    }

    pub fn metrics(&self) -> &Metrics {
        &self.state.metrics
    }

    /// Serve forever, one thread per in-flight request. PoC-grade on purpose:
    /// the concurrency model is the simplest one that cannot deadlock, and
    /// the interesting properties live in `handle`, which is what the tests
    /// exercise.
    pub fn run(self) {
        let server = Arc::new(self.server);
        loop {
            let Ok(request) = server.recv() else { break };
            let state = Arc::clone(&self.state);
            std::thread::spawn(move || handle(&state, request));
        }
    }
}

fn header_value<'a>(request: &'a tiny_http::Request, name: &str) -> Option<&'a str> {
    request
        .headers()
        .iter()
        .find(|h| h.field.as_str().as_str().eq_ignore_ascii_case(name))
        .map(|h| h.value.as_str())
}

fn respond(request: tiny_http::Request, response: Response<impl Read>) {
    // A client that hung up mid-response is its own problem, not a proxy
    // crash. Everything before this point already updated the metrics.
    let _ = request.respond(response);
}

/// Everything the proxy needs from the origin response's head, snapshotted
/// BEFORE `into_reader()` consumes the response.
struct OriginHead {
    status: u16,
    /// All headers except hop-by-hop and the ones the proxy recomputes.
    forwardable: Vec<(String, String)>,
    content_type: String,
    already_encoded: bool,
    no_transform: bool,
    vary: Option<String>,
    validator: Option<String>,
    content_length: Option<usize>,
}

fn snapshot(resp: &OriginResponse) -> OriginHead {
    let mut forwardable = Vec::new();
    let mut vary = None;
    let mut content_length = None;
    for (name, value) in &resp.headers {
        if name.eq_ignore_ascii_case("content-length") {
            content_length = value.parse().ok();
        }
        if name.eq_ignore_ascii_case("vary") {
            vary = Some(value.to_owned());
            continue;
        }
        if skip_header(name, false) {
            continue;
        }
        forwardable.push((name.clone(), value.to_owned()));
    }
    OriginHead {
        status: resp.status,
        forwardable,
        content_type: resp.header("content-type").unwrap_or("").to_owned(),
        already_encoded: resp.header("content-encoding").is_some(),
        no_transform: resp
            .header("cache-control")
            .unwrap_or("")
            .to_ascii_lowercase()
            .contains("no-transform"),
        vary,
        validator: resp
            .header("etag")
            .or_else(|| resp.header("last-modified"))
            .map(str::to_owned),
        content_length,
    }
}

fn handle(state: &State, mut request: tiny_http::Request) {
    state.metrics.requests_total.fetch_add(1, Ordering::Relaxed);

    if request.url() == METRICS_PATH {
        let body = state.metrics.render();
        let response = Response::from_data(body.into_bytes())
            .with_header(Header::from_bytes("Content-Type", "text/plain; version=0.0.4").unwrap());
        respond(request, response);
        return;
    }

    let wants = wants_cbm(header_value(&request, "accept-encoding"));
    let method = request.method().clone();
    let url = request.url().to_owned();

    // Build the origin request: client headers minus hop-by-hop, minus
    // Accept-Encoding (replaced below), minus Host (the client set it to
    // reach the proxy; the origin client derives its own from the authority),
    // minus Content-Length (recomputed when a body is forwarded).
    let mut origin_headers: Vec<(String, String)> = Vec::new();
    for h in request.headers() {
        let name = h.field.as_str().as_str();
        if skip_header(name, false)
            || name.eq_ignore_ascii_case("accept-encoding")
            || name.eq_ignore_ascii_case("host")
        {
            continue;
        }
        origin_headers.push((name.to_owned(), h.value.as_str().to_owned()));
    }
    // GET from a cbm client fetches identity so there are raw bytes to
    // encode; everything else forwards the client's own preference with the
    // cbm token stripped, and the origin's choice passes through.
    let compress_leg = wants && method == Method::Get;
    let forwarded_accept = if compress_leg {
        "identity".to_owned()
    } else {
        header_value(&request, "accept-encoding")
            .map(strip_cbm)
            .unwrap_or_default()
    };
    if !forwarded_accept.is_empty() {
        origin_headers.push(("Accept-Encoding".to_owned(), forwarded_accept));
    }

    let request_body = if matches!(method, Method::Get | Method::Head) {
        None
    } else {
        let mut body = Vec::new();
        if request.as_reader().read_to_end(&mut body).is_err() {
            respond(
                request,
                Response::from_string("bad request body").with_status_code(400),
            );
            return;
        }
        Some(body)
    };

    let origin_resp = match origin::fetch(
        &state.authority,
        method.as_str(),
        &url,
        &origin_headers,
        request_body.as_deref(),
    ) {
        Ok(r) => r,
        Err(e) => {
            state
                .metrics
                .origin_errors_total
                .fetch_add(1, Ordering::Relaxed);
            respond(
                request,
                Response::from_string(format!("cubrimd: origin unreachable: {e}"))
                    .with_status_code(502),
            );
            return;
        }
    };

    let head = snapshot(&origin_resp);
    let eligible = compress_leg
        && head.status == 200
        && compressible(&head.content_type)
        && !head.already_encoded
        && !head.no_transform;

    if !eligible {
        passthrough(state, request, origin_resp, head);
        return;
    }

    // Cached variant? The validator has to match the representation the
    // origin is serving RIGHT NOW — a hit on a stale validator is a miss.
    if let Some(validator) = &head.validator {
        let hit = state
            .cache
            .lock()
            .expect("cache lock")
            .get(request.url(), validator);
        if let Some(frame) = hit {
            state
                .metrics
                .cache_hits_total
                .fetch_add(1, Ordering::Relaxed);
            state
                .metrics
                .cbm_responses_total
                .fetch_add(1, Ordering::Relaxed);
            state
                .metrics
                .cbm_bytes_total
                .fetch_add(frame.len() as u64, Ordering::Relaxed);
            respond_cbm(request, &head, frame.as_slice().to_vec());
            return;
        }
        state
            .metrics
            .cache_misses_total
            .fetch_add(1, Ordering::Relaxed);
    }

    // Read the body with a hard cap. Over the cap the response streams
    // through unencoded — the buffered prefix chained with the untouched
    // remainder — because first-byte latency on a huge dynamic body is worth
    // more than its ratio.
    let cap = state.config.max_body_bytes;
    let mut body = Vec::new();
    let mut reader = origin_resp.body;
    if reader
        .by_ref()
        .take(cap as u64 + 1)
        .read_to_end(&mut body)
        .is_err()
    {
        state
            .metrics
            .origin_errors_total
            .fetch_add(1, Ordering::Relaxed);
        respond(
            request,
            Response::from_string("cubrimd: origin body read failed").with_status_code(502),
        );
        return;
    }
    if body.len() > cap {
        state
            .metrics
            .passthrough_total
            .fetch_add(1, Ordering::Relaxed);
        let headers = identity_headers(&head);
        let chained = std::io::Read::chain(std::io::Cursor::new(body), reader);
        respond(
            request,
            Response::new(head.status.into(), headers, chained, None, None),
        );
        return;
    }

    state
        .metrics
        .original_bytes_total
        .fetch_add(body.len() as u64, Ordering::Relaxed);

    // The reverse proxy is the near-realtime consumer of the Web Profile.
    // Keep the density-first static encoder available to archive callers, but
    // do not spend its shortest-path parse budget on a request path.
    let frame = encode_web_dynamic(&body, state.config.block_size).unwrap_or_default();

    // The rail can still hand back a frame that is not worth its header
    // bytes; shipping a larger "compressed" response is negative value, so
    // identity wins the comparison outright.
    if frame.len() >= body.len() {
        state
            .metrics
            .identity_eligible_total
            .fetch_add(1, Ordering::Relaxed);
        let headers = identity_headers(&head);
        let len = body.len();
        respond(
            request,
            Response::new(
                head.status.into(),
                headers,
                std::io::Cursor::new(body),
                Some(len),
                None,
            ),
        );
        return;
    }

    if let Some(validator) = &head.validator {
        state.cache.lock().expect("cache lock").insert(
            request.url().to_owned(),
            validator.clone(),
            Arc::new(frame.clone()),
        );
    }
    state
        .metrics
        .cbm_responses_total
        .fetch_add(1, Ordering::Relaxed);
    state
        .metrics
        .cbm_bytes_total
        .fetch_add(frame.len() as u64, Ordering::Relaxed);
    respond_cbm(request, &head, frame);
}

/// Headers for an eligible response served as identity: forwardable set plus
/// the merged `Vary` — the representation still depends on `Accept-Encoding`
/// at this hop, so the cache key must too.
fn identity_headers(head: &OriginHead) -> Vec<Header> {
    let mut headers: Vec<Header> = head
        .forwardable
        .iter()
        .filter_map(|(n, v)| Header::from_bytes(n.as_bytes(), v.as_bytes()).ok())
        .collect();
    let merged = merge_vary(head.vary.as_deref());
    headers.push(Header::from_bytes("Vary", merged.as_bytes()).unwrap());
    headers
}

/// Serve a Web Profile frame as `Content-Encoding: cbm`. The origin's `ETag`
/// is dropped rather than forwarded: an entity tag names a representation,
/// and this is a different one.
fn respond_cbm(request: tiny_http::Request, head: &OriginHead, frame: Vec<u8>) {
    let mut headers: Vec<Header> = head
        .forwardable
        .iter()
        .filter(|(n, _)| !n.eq_ignore_ascii_case("etag"))
        .filter_map(|(n, v)| Header::from_bytes(n.as_bytes(), v.as_bytes()).ok())
        .collect();
    headers.push(Header::from_bytes("Content-Encoding", CODING.as_bytes()).unwrap());
    let merged = merge_vary(head.vary.as_deref());
    headers.push(Header::from_bytes("Vary", merged.as_bytes()).unwrap());
    let len = frame.len();
    respond(
        request,
        Response::new(
            head.status.into(),
            headers,
            std::io::Cursor::new(frame),
            Some(len),
            None,
        ),
    );
}

fn passthrough(
    state: &State,
    request: tiny_http::Request,
    origin_resp: OriginResponse,
    head: OriginHead,
) {
    state
        .metrics
        .passthrough_total
        .fetch_add(1, Ordering::Relaxed);
    let mut headers: Vec<Header> = head
        .forwardable
        .iter()
        .filter_map(|(n, v)| Header::from_bytes(n.as_bytes(), v.as_bytes()).ok())
        .collect();
    // A compressible resource varies on Accept-Encoding at this hop whichever
    // representation this particular client got; anything else keeps the
    // origin's Vary untouched.
    if compressible(&head.content_type) {
        headers
            .push(Header::from_bytes("Vary", merge_vary(head.vary.as_deref()).as_bytes()).unwrap());
    } else if let Some(v) = &head.vary {
        headers.push(Header::from_bytes("Vary", v.as_bytes()).unwrap());
    }
    // The de-chunked body streams through; when the origin framed it with
    // Content-Length that length still holds, otherwise tiny_http re-frames.
    let response = Response::new(
        head.status.into(),
        headers,
        origin_resp.body,
        head.content_length,
        None,
    );
    respond(request, response);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_plain_list() {
        assert_eq!(
            parse_accept_encoding("cbm, br, gzip"),
            vec![
                ("cbm".into(), 1.0),
                ("br".into(), 1.0),
                ("gzip".into(), 1.0)
            ]
        );
    }

    #[test]
    fn parse_weights_case_and_unknown_params() {
        assert_eq!(
            parse_accept_encoding("CBM;level=9;q=0.5, GZIP ; q=0.08"),
            vec![("cbm".into(), 0.5), ("gzip".into(), 0.08)]
        );
    }

    #[test]
    fn parse_drops_malformed_members() {
        assert!(parse_accept_encoding("cbm;q=2").is_empty());
        assert!(parse_accept_encoding("cbm;q=0.5001").is_empty());
        assert!(parse_accept_encoding("cbm;q").is_empty());
        assert!(parse_accept_encoding("cb m").is_empty());
        assert_eq!(parse_accept_encoding(" , cbm").len(), 1);
    }

    #[test]
    fn parse_first_occurrence_wins() {
        assert_eq!(
            parse_accept_encoding("cbm;q=0, cbm"),
            vec![("cbm".into(), 0.0)]
        );
    }

    #[test]
    fn wants_cbm_matrix() {
        assert!(!wants_cbm(None));
        assert!(!wants_cbm(Some("")));
        assert!(wants_cbm(Some("cbm, br, gzip")));
        assert!(wants_cbm(Some("CBM")));
        assert!(!wants_cbm(Some("gzip, br")));
        assert!(!wants_cbm(Some("cbm;q=0")));
        assert!(wants_cbm(Some("cbm;q=0.1, gzip")));
        assert!(!wants_cbm(Some("*"))); // wildcard never selects cbm
        assert!(!wants_cbm(Some("cbm;q=broken")));
    }

    #[test]
    fn strip_cbm_keeps_the_rest() {
        assert_eq!(strip_cbm("cbm, br;q=0.9, gzip"), "br;q=0.9, gzip");
        assert_eq!(strip_cbm("CBM;q=0.5"), "");
        assert_eq!(strip_cbm("gzip"), "gzip");
    }

    #[test]
    fn compressible_allowlist() {
        assert!(compressible("text/html; charset=utf-8"));
        assert!(compressible("application/json"));
        assert!(compressible("image/svg+xml"));
        assert!(compressible("application/wasm"));
        assert!(compressible("application/ld+json"));
        assert!(!compressible("image/png"));
        assert!(!compressible("video/mp4"));
        assert!(!compressible("font/woff2"));
        assert!(!compressible("application/octet-stream"));
    }

    #[test]
    fn vary_merge() {
        assert_eq!(merge_vary(None), "Accept-Encoding");
        assert_eq!(merge_vary(Some("Accept-Encoding")), "Accept-Encoding");
        assert_eq!(merge_vary(Some("accept-encoding")), "accept-encoding");
        assert_eq!(merge_vary(Some("Origin")), "Origin, Accept-Encoding");
        assert_eq!(merge_vary(Some("*")), "*");
    }

    #[test]
    fn cache_fifo_and_validator() {
        let mut c = VariantCache::new(2);
        c.insert("/a".into(), "v1".into(), Arc::new(vec![1]));
        c.insert("/b".into(), "v1".into(), Arc::new(vec![2]));
        assert!(c.get("/a", "v1").is_some());
        assert!(c.get("/a", "v2").is_none(), "stale validator must miss");
        c.insert("/c".into(), "v1".into(), Arc::new(vec![3]));
        assert!(c.get("/a", "v1").is_none(), "FIFO evicts the oldest");
        assert!(c.get("/b", "v1").is_some());
        assert!(c.get("/c", "v1").is_some());
    }
}
