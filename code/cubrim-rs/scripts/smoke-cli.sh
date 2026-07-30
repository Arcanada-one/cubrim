#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${1:-${ROOT}/target/release/cubrim}"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${ROOT}/Cargo.toml" | head -n1)"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ -x "${BIN}" ]] || die "binary is not executable: ${BIN}"

TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/cubrim-smoke.XXXXXX")"
trap 'rm -rf "${TMPDIR}"' EXIT

export CUBRIM_ACCEPT_LICENSE=1
export CUBRIM_STATE_DIR="${TMPDIR}/state"
export CUBRIM_API_BASE_URL="http://127.0.0.1:9"

"${BIN}" --help > "${TMPDIR}/help.txt"
"${BIN}" --version > "${TMPDIR}/version.txt"

grep -q 'Usage:' "${TMPDIR}/help.txt" || die "--help output missing Usage"
grep -q 'compress' "${TMPDIR}/help.txt" || die "--help output missing compress"
grep -q 'decompress' "${TMPDIR}/help.txt" || die "--help output missing decompress"
grep -q "${VERSION}" "${TMPDIR}/version.txt" || die "--version output missing ${VERSION}"

for _ in $(seq 1 512); do
  printf 'CUBR CLI smoke test line with repeated text and numbers 0123456789\n'
done > "${TMPDIR}/input.txt"

"${BIN}" compress "${TMPDIR}/input.txt" "${TMPDIR}/input.cubr" 2> "${TMPDIR}/compress.err"
"${BIN}" decompress "${TMPDIR}/input.cubr" "${TMPDIR}/output.txt" 2> "${TMPDIR}/decompress.err"
cmp "${TMPDIR}/input.txt" "${TMPDIR}/output.txt"

grep -q 'compressed:' "${TMPDIR}/compress.err" || die "compress stderr missing compressed line"
grep -q 'ratio=' "${TMPDIR}/compress.err" || die "compress stderr missing ratio"
grep -q 'time_ms=' "${TMPDIR}/compress.err" || die "compress stderr missing time_ms"
grep -q 'decompressed:' "${TMPDIR}/decompress.err" || die "decompress stderr missing decompressed line"
grep -q 'time_ms=' "${TMPDIR}/decompress.err" || die "decompress stderr missing time_ms"

cat "${TMPDIR}/version.txt"
cat "${TMPDIR}/compress.err"
cat "${TMPDIR}/decompress.err"
printf 'CLI_SMOKE_OK %s\n' "${BIN}"
