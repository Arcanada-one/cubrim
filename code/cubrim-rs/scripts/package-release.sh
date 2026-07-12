#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:?target triple required}"
OS="${2:?os label required}"
ARCH="${3:?arch label required}"
EXT="${4:-tar.gz}"
BIN_NAME="cubrim"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${ROOT}/Cargo.toml" | head -n1)"
DIST_DIR="${ROOT}/dist/release"
STAGE="${DIST_DIR}/stage-${TARGET}"
ASSET_BASE="cubrim-v${VERSION}-${OS}-${ARCH}"

rm -rf "${STAGE}"
mkdir -p "${STAGE}" "${DIST_DIR}"

BIN_PATH="${ROOT}/target/${TARGET}/release/${BIN_NAME}"
if [[ "${TARGET}" == *windows* ]]; then
  BIN_PATH="${BIN_PATH}.exe"
fi
[[ -f "${BIN_PATH}" ]] || { echo "missing built binary: ${BIN_PATH}" >&2; exit 1; }

cp "${BIN_PATH}" "${STAGE}/"
cp "${ROOT}/LICENSE-SHORT.txt" "${STAGE}/LICENSE.txt"
if [[ -f "${ROOT}/LICENSE-COMMERCIAL.md" ]]; then
  cp "${ROOT}/LICENSE-COMMERCIAL.md" "${STAGE}/LICENSE-COMMERCIAL.md"
fi
cp "${ROOT}/docs/cli.md" "${STAGE}/README.txt"

ARCHIVE_PATH="${DIST_DIR}/${ASSET_BASE}.${EXT}"
rm -f "${ARCHIVE_PATH}" "${ARCHIVE_PATH}.sha256" "${ARCHIVE_PATH}.size"

if [[ "${EXT}" == "zip" ]]; then
  (
    cd "${STAGE}"
    zip -q -r "${ARCHIVE_PATH}" .
  )
else
  tar -C "${STAGE}" -czf "${ARCHIVE_PATH}" .
fi

sha256sum "${ARCHIVE_PATH}" | awk '{print $1}' > "${ARCHIVE_PATH}.sha256"
stat --printf='%s\n' "${ARCHIVE_PATH}" > "${ARCHIVE_PATH}.size"

printf '%s\n' "${ARCHIVE_PATH}"
