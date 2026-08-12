//! End-to-end: a real origin server, the real proxy, real HTTP between them.
//!
//! The origin records the `Accept-Encoding` it was sent per request, because
//! half of the proxy's contract is what the ORIGIN sees: `identity` on the
//! compress leg (so there are raw bytes to encode), the client's own list
//! with the `cbm` token stripped on every other leg.
//!
//! The test client is the crate's own `origin::fetch` — raw HTTP/1.1 over a
//! socket. Not incidental: a convenience client (ureq with unified features)
//! transparently decompresses recognised codings and deletes the header,
//! which would make the passthrough assertions here test the client instead
//! of the proxy.

use std::collections::HashMap;
use std::io::Read;
use std::sync::{Arc, Mutex};

use cubrimd::origin::{fetch, OriginResponse};
use cubrimd::{Config, Proxy, METRICS_PATH};

/// Compressible enough to beat the frame header comfortably.
fn html_body() -> Vec<u8> {
    let row = "<tr><td class=\"cell\">value</td><td class=\"cell\">another value</td></tr>\n";
    let mut body = String::from("<!doctype html><html><body><table>\n");
    for i in 0..800 {
        body.push_str(&format!("<!-- row {i} -->{row}"));
    }
    body.push_str("</table></body></html>\n");
    body.into_bytes()
}

struct Origin {
    port: u16,
    seen: Arc<Mutex<HashMap<String, String>>>,
    hits: Arc<Mutex<HashMap<String, u32>>>,
}

fn spawn_origin() -> Origin {
    let server = tiny_http::Server::http("127.0.0.1:0").expect("bind origin");
    let port = match server.server_addr() {
        tiny_http::ListenAddr::IP(addr) => addr.port(),
        _ => unreachable!(),
    };
    let seen: Arc<Mutex<HashMap<String, String>>> = Arc::default();
    let hits: Arc<Mutex<HashMap<String, u32>>> = Arc::default();
    let seen2 = Arc::clone(&seen);
    let hits2 = Arc::clone(&hits);
    std::thread::spawn(move || {
        for mut request in server.incoming_requests() {
            let url = request.url().to_owned();
            let accept = request
                .headers()
                .iter()
                .find(|h| {
                    h.field
                        .as_str()
                        .as_str()
                        .eq_ignore_ascii_case("accept-encoding")
                })
                .map(|h| h.value.as_str().to_owned())
                .unwrap_or_default();
            seen2.lock().unwrap().insert(url.clone(), accept);
            *hits2.lock().unwrap().entry(url.clone()).or_insert(0) += 1;

            let header = |n: &str, v: &str| tiny_http::Header::from_bytes(n, v).unwrap();
            let response = match url.as_str() {
                "/page.html" => tiny_http::Response::from_data(html_body())
                    .with_header(header("Content-Type", "text/html; charset=utf-8"))
                    .with_header(header("ETag", "\"page-v1\""))
                    .with_header(header("X-Origin", "yes")),
                "/data.bin" => tiny_http::Response::from_data(vec![0u8; 4096])
                    .with_header(header("Content-Type", "application/octet-stream")),
                "/pre.gz" => tiny_http::Response::from_data(b"pretend-gzip-bytes".to_vec())
                    .with_header(header("Content-Type", "text/html"))
                    .with_header(header("Content-Encoding", "gzip")),
                "/notransform.html" => tiny_http::Response::from_data(html_body())
                    .with_header(header("Content-Type", "text/html"))
                    .with_header(header("Cache-Control", "no-transform")),
                "/redirect" => tiny_http::Response::from_data(Vec::new())
                    .with_status_code(302)
                    .with_header(header("Location", "/page.html")),
                "/post" => {
                    let mut body = Vec::new();
                    request.as_reader().read_to_end(&mut body).unwrap();
                    tiny_http::Response::from_data(body)
                        .with_header(header("Content-Type", "text/plain"))
                }
                _ => tiny_http::Response::from_data(b"nope".to_vec()).with_status_code(404),
            };
            let _ = request.respond(response);
        }
    });
    Origin { port, seen, hits }
}

struct Rig {
    origin: Origin,
    proxy_authority: String,
}

fn rig() -> Rig {
    let origin = spawn_origin();
    let proxy = Proxy::bind(
        "127.0.0.1:0",
        Config {
            origin: format!("http://127.0.0.1:{}", origin.port),
            ..Config::default()
        },
    )
    .expect("bind proxy");
    let proxy_authority = format!("127.0.0.1:{}", proxy.port());
    std::thread::spawn(move || proxy.run());
    Rig {
        origin,
        proxy_authority,
    }
}

impl Rig {
    fn get(&self, path: &str, accept_encoding: Option<&str>) -> OriginResponse {
        let headers: Vec<(String, String)> = accept_encoding
            .map(|ae| vec![("Accept-Encoding".to_owned(), ae.to_owned())])
            .unwrap_or_default();
        fetch(&self.proxy_authority, "GET", path, &headers, None).expect("request")
    }

    fn body(resp: OriginResponse) -> Vec<u8> {
        let mut out = Vec::new();
        let mut body = resp.body;
        body.read_to_end(&mut out).unwrap();
        out
    }

    fn origin_saw(&self, path: &str) -> String {
        self.origin
            .seen
            .lock()
            .unwrap()
            .get(path)
            .cloned()
            .unwrap_or_default()
    }
}

#[test]
fn cbm_client_gets_cbm_and_it_round_trips() {
    let rig = rig();
    let resp = rig.get("/page.html", Some("cbm, br, gzip"));
    assert_eq!(resp.status, 200);
    assert_eq!(resp.header("content-encoding"), Some("cbm"));
    assert_eq!(
        resp.header("content-type"),
        Some("text/html; charset=utf-8")
    );
    assert_eq!(
        resp.header("x-origin"),
        Some("yes"),
        "origin headers forwarded"
    );
    assert!(
        resp.header("vary")
            .unwrap_or("")
            .to_ascii_lowercase()
            .contains("accept-encoding"),
        "cbm response must vary on Accept-Encoding"
    );
    assert_eq!(
        resp.header("etag"),
        None,
        "an entity tag names a representation, and this is a different one"
    );
    let frame = Rig::body(resp);
    let original = html_body();
    assert!(
        frame.len() < original.len(),
        "frame {} must beat identity {}",
        frame.len(),
        original.len()
    );
    assert_eq!(
        cubrim::decode(&frame).expect("decode"),
        original,
        "byte-exact round trip through the proxy"
    );
    assert_eq!(
        rig.origin_saw("/page.html"),
        "identity",
        "compress leg must fetch raw bytes from the origin"
    );
}

#[test]
fn plain_client_gets_identity_with_vary_and_stripped_token() {
    let rig = rig();
    let resp = rig.get("/page.html", Some("cbm;q=0, gzip"));
    assert_eq!(resp.status, 200);
    assert_eq!(resp.header("content-encoding"), None);
    assert!(
        resp.header("vary")
            .unwrap_or("")
            .to_ascii_lowercase()
            .contains("accept-encoding"),
        "identity representation of a negotiable resource still varies"
    );
    assert_eq!(Rig::body(resp), html_body(), "identity body byte-exact");
    assert_eq!(
        rig.origin_saw("/page.html"),
        "gzip",
        "cbm token stripped, the rest forwarded verbatim"
    );
}

#[test]
fn wildcard_never_selects_cbm() {
    let rig = rig();
    let resp = rig.get("/page.html", Some("*"));
    assert_eq!(resp.header("content-encoding"), None);
    assert_eq!(Rig::body(resp), html_body());
}

#[test]
fn absent_accept_encoding_gets_identity() {
    let rig = rig();
    let resp = rig.get("/page.html", None);
    assert_eq!(resp.header("content-encoding"), None);
    assert_eq!(Rig::body(resp), html_body());
}

#[test]
fn non_compressible_type_is_untouched() {
    let rig = rig();
    let resp = rig.get("/data.bin", Some("cbm"));
    assert_eq!(resp.status, 200);
    assert_eq!(resp.header("content-encoding"), None);
    assert_eq!(
        resp.header("vary"),
        None,
        "a type the proxy never negotiates does not vary on Accept-Encoding"
    );
    assert_eq!(Rig::body(resp), vec![0u8; 4096]);
}

#[test]
fn origin_encoded_response_passes_through_untouched() {
    let rig = rig();
    let resp = rig.get("/pre.gz", Some("cbm"));
    assert_eq!(
        resp.header("content-encoding"),
        Some("gzip"),
        "never double-encode"
    );
    assert_eq!(Rig::body(resp), b"pretend-gzip-bytes".to_vec());
}

#[test]
fn no_transform_is_respected() {
    let rig = rig();
    let resp = rig.get("/notransform.html", Some("cbm"));
    assert_eq!(resp.header("content-encoding"), None);
    assert_eq!(Rig::body(resp), html_body());
}

#[test]
fn redirects_pass_through_unfollowed() {
    let rig = rig();
    let resp = rig.get("/redirect", Some("cbm"));
    assert_eq!(resp.status, 302);
    assert_eq!(resp.header("location"), Some("/page.html"));
}

#[test]
fn post_is_forwarded_and_never_compressed() {
    let rig = rig();
    let resp = fetch(
        &rig.proxy_authority,
        "POST",
        "/post",
        &[("Accept-Encoding".to_owned(), "cbm".to_owned())],
        Some(b"echo me"),
    )
    .unwrap();
    assert_eq!(resp.header("content-encoding"), None);
    assert_eq!(Rig::body(resp), b"echo me".to_vec());
}

#[test]
fn second_request_is_served_from_the_variant_cache() {
    let rig = rig();
    let first = Rig::body(rig.get("/page.html", Some("cbm")));
    assert_eq!(
        *rig.origin.hits.lock().unwrap().get("/page.html").unwrap(),
        1
    );
    let second = Rig::body(rig.get("/page.html", Some("cbm")));
    assert_eq!(first, second, "cache hit must serve identical frame bytes");
    // The origin is still consulted for the validator (the cache guards
    // freshness, it does not invent it), so origin hits go up — the metrics
    // prove the frame came from the cache, not a second encode.
    let metrics = String::from_utf8(Rig::body(rig.get(METRICS_PATH, None))).unwrap();
    assert!(
        metrics.contains("cubrimd_cache_hits_total 1"),
        "expected one cache hit, got:\n{metrics}"
    );
    assert!(
        metrics.contains("cubrimd_cbm_responses_total 2"),
        "{metrics}"
    );
}

#[test]
fn metrics_endpoint_serves_prometheus_text() {
    let rig = rig();
    let resp = rig.get(METRICS_PATH, None);
    assert_eq!(resp.status, 200);
    assert!(resp
        .header("content-type")
        .unwrap_or("")
        .starts_with("text/plain"));
    let body = String::from_utf8(Rig::body(resp)).unwrap();
    assert!(body.contains("cubrimd_requests_total"));
}

#[test]
fn dead_origin_is_a_502_not_a_hang_or_a_crash() {
    // Port 1 on loopback: reserved, nothing listens there.
    let proxy = Proxy::bind(
        "127.0.0.1:0",
        Config {
            origin: "http://127.0.0.1:1".to_owned(),
            ..Config::default()
        },
    )
    .expect("bind proxy");
    let authority = format!("127.0.0.1:{}", proxy.port());
    std::thread::spawn(move || proxy.run());
    let resp = fetch(&authority, "GET", "/x", &[], None).unwrap();
    assert_eq!(resp.status, 502);
}
