//! Minimal HTTP/1.1 origin client.
//!
//! Hand-rolled over `TcpStream` ON PURPOSE. The obvious dependency (ureq)
//! transparently decompresses any `Content-Encoding` its compiled features
//! recognise and deletes the header while doing so — and feature unification
//! with the `cubrim` crate compiles those features in whether this crate asks
//! for them or not. A proxy whose fallback contract is "the origin's brotli /
//! zstd / gzip passes through byte-untouched" cannot be built on a client
//! that silently re-inflates one of those codings. Measured, not assumed:
//! a `Content-Encoding: gzip` response fetched through the unified ureq
//! build came back header-stripped.
//!
//! Scope, stated: `http://` origins only, one request per connection
//! (`Connection: close`), no redirect following (they pass through), bodies
//! framed by `Content-Length`, `Transfer-Encoding: chunked` (de-chunked here
//! — transfer framing is hop-by-hop, unlike content codings), or EOF.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::time::Duration;

/// Idle-read/write ceiling per origin connection. A hung origin turns into a
/// visible 502, not a stuck proxy thread.
const IO_TIMEOUT: Duration = Duration::from_secs(30);
/// Response head (status line + headers) ceiling.
const MAX_HEAD_BYTES: usize = 64 * 1024;

pub struct OriginResponse {
    pub status: u16,
    /// Headers in wire order, duplicates preserved (`Set-Cookie` is real).
    pub headers: Vec<(String, String)>,
    pub body: Body,
}

impl OriginResponse {
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(n, _)| n.eq_ignore_ascii_case(name))
            .map(|(_, v)| v.as_str())
    }
}

/// `authority` is the `host:port` part of the origin URL.
pub fn fetch(
    authority: &str,
    method: &str,
    path_query: &str,
    headers: &[(String, String)],
    body: Option<&[u8]>,
) -> std::io::Result<OriginResponse> {
    let stream = TcpStream::connect(authority)?;
    stream.set_read_timeout(Some(IO_TIMEOUT))?;
    stream.set_write_timeout(Some(IO_TIMEOUT))?;

    let mut request =
        format!("{method} {path_query} HTTP/1.1\r\nHost: {authority}\r\nConnection: close\r\n");
    for (name, value) in headers {
        request.push_str(&format!("{name}: {value}\r\n"));
    }
    if let Some(body) = body {
        request.push_str(&format!("Content-Length: {}\r\n", body.len()));
    }
    request.push_str("\r\n");

    let mut writer = stream.try_clone()?;
    writer.write_all(request.as_bytes())?;
    if let Some(body) = body {
        writer.write_all(body)?;
    }
    writer.flush()?;

    let mut reader = BufReader::new(stream);
    let status_line = read_head_line(&mut reader)?;
    let status = parse_status(&status_line)?;

    let mut headers_out: Vec<(String, String)> = Vec::new();
    let mut head_bytes = status_line.len();
    loop {
        let line = read_head_line(&mut reader)?;
        head_bytes += line.len();
        if head_bytes > MAX_HEAD_BYTES {
            return Err(bad("response head too large"));
        }
        if line.is_empty() {
            break;
        }
        let Some((name, value)) = line.split_once(':') else {
            return Err(bad("malformed header line"));
        };
        headers_out.push((name.trim().to_owned(), value.trim().to_owned()));
    }

    let chunked = headers_out
        .iter()
        .filter(|(n, _)| n.eq_ignore_ascii_case("transfer-encoding"))
        .any(|(_, v)| v.to_ascii_lowercase().contains("chunked"));
    let content_length: Option<u64> = headers_out
        .iter()
        .find(|(n, _)| n.eq_ignore_ascii_case("content-length"))
        .and_then(|(_, v)| v.trim().parse().ok());

    let bodyless = method.eq_ignore_ascii_case("HEAD") || matches!(status, 100..=199 | 204 | 304);
    let body = if bodyless {
        Body::Empty
    } else if chunked {
        Body::Chunked(ChunkedReader::new(reader))
    } else if let Some(length) = content_length {
        Body::Length(reader.take(length))
    } else {
        Body::Eof(reader)
    };

    Ok(OriginResponse {
        status,
        headers: headers_out,
        body,
    })
}

fn bad(message: &str) -> std::io::Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, message)
}

fn parse_status(line: &str) -> std::io::Result<u16> {
    let mut parts = line.split(' ');
    match (parts.next(), parts.next()) {
        (Some(version), Some(code)) if version.starts_with("HTTP/1.") => {
            code.parse().map_err(|_| bad("bad status code"))
        }
        _ => Err(bad("bad status line")),
    }
}

/// One CRLF-terminated head line, CRLF stripped. Bounded by MAX_HEAD_BYTES
/// via the caller's accounting; `read_line` itself is bounded by take.
fn read_head_line<R: BufRead>(reader: &mut R) -> std::io::Result<String> {
    let mut line = String::new();
    reader
        .by_ref()
        .take(MAX_HEAD_BYTES as u64)
        .read_line(&mut line)?;
    if !line.ends_with('\n') {
        return Err(bad("truncated response head"));
    }
    while line.ends_with('\n') || line.ends_with('\r') {
        line.pop();
    }
    Ok(line)
}

pub enum Body {
    Empty,
    Length(std::io::Take<BufReader<TcpStream>>),
    Chunked(ChunkedReader<BufReader<TcpStream>>),
    Eof(BufReader<TcpStream>),
}

impl Read for Body {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        match self {
            Body::Empty => Ok(0),
            Body::Length(r) => r.read(buf),
            Body::Chunked(r) => r.read(buf),
            Body::Eof(r) => r.read(buf),
        }
    }
}

/// `Transfer-Encoding: chunked` decoder. Transfer framing is hop-by-hop, so
/// removing it here is correct in exactly the way removing a content coding
/// would be wrong. Trailers are read and discarded.
pub struct ChunkedReader<R: BufRead> {
    inner: R,
    /// Bytes left in the current chunk's data.
    remaining: u64,
    /// Seen the terminal zero-size chunk.
    done: bool,
    /// Whether the *first* chunk header is still unread (no preceding CRLF).
    first: bool,
}

impl<R: BufRead> ChunkedReader<R> {
    pub fn new(inner: R) -> Self {
        Self {
            inner,
            remaining: 0,
            done: false,
            first: true,
        }
    }

    fn next_chunk(&mut self) -> std::io::Result<()> {
        if !self.first {
            // Consume the CRLF that terminates the previous chunk's data.
            let mut crlf = [0u8; 2];
            self.inner.read_exact(&mut crlf)?;
            if &crlf != b"\r\n" {
                return Err(bad("chunk data not CRLF-terminated"));
            }
        }
        self.first = false;
        let line = read_head_line(&mut self.inner)?;
        let size_hex = line.split(';').next().unwrap_or("").trim();
        let size = u64::from_str_radix(size_hex, 16).map_err(|_| bad("bad chunk size"))?;
        if size == 0 {
            // Trailer section: zero or more header lines, then an empty line.
            loop {
                if read_head_line(&mut self.inner)?.is_empty() {
                    break;
                }
            }
            self.done = true;
        }
        self.remaining = size;
        Ok(())
    }
}

impl<R: BufRead> Read for ChunkedReader<R> {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.done {
            return Ok(0);
        }
        if self.remaining == 0 {
            self.next_chunk()?;
            if self.done {
                return Ok(0);
            }
        }
        let want = buf.len().min(self.remaining as usize);
        let got = self.inner.read(&mut buf[..want])?;
        if got == 0 {
            return Err(bad("chunk truncated"));
        }
        self.remaining -= got as u64;
        Ok(got)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn dechunk(wire: &[u8]) -> std::io::Result<Vec<u8>> {
        let mut out = Vec::new();
        ChunkedReader::new(Cursor::new(wire.to_vec())).read_to_end(&mut out)?;
        Ok(out)
    }

    #[test]
    fn chunked_basic() {
        let wire = b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n";
        assert_eq!(dechunk(wire).unwrap(), b"Wikipedia");
    }

    #[test]
    fn chunked_with_extensions_and_trailers() {
        let wire = b"4;ext=1\r\nWiki\r\n0\r\nX-Trailer: v\r\n\r\n";
        assert_eq!(dechunk(wire).unwrap(), b"Wiki");
    }

    #[test]
    fn chunked_empty_body() {
        assert_eq!(dechunk(b"0\r\n\r\n").unwrap(), b"");
    }

    #[test]
    fn chunked_truncation_is_an_error_not_a_short_body() {
        assert!(dechunk(b"5\r\nWi").is_err());
        assert!(dechunk(b"4\r\nWiki\r\n").is_err(), "missing terminal chunk");
    }

    #[test]
    fn chunked_bad_size_is_an_error() {
        assert!(dechunk(b"zz\r\nWiki\r\n0\r\n\r\n").is_err());
    }

    #[test]
    fn status_line_parses() {
        assert_eq!(parse_status("HTTP/1.1 200 OK").unwrap(), 200);
        assert_eq!(parse_status("HTTP/1.0 404 Not Found").unwrap(), 404);
        assert!(parse_status("ICY 200 OK").is_err());
    }
}
