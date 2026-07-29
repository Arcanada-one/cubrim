#!/usr/bin/env bash
set -euo pipefail

package_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
workspace="${1:-}"
if [[ -z "$workspace" || "$workspace" != /* || "$workspace" == "/" ]]; then
  printf 'workspace must be an absolute non-root path\n' >&2
  exit 64
fi
install -d -m 0700 "$workspace"
workspace="$(cd -- "$workspace" && pwd -P)"
if [[ -e "$workspace/corpus" || -e "$workspace/tools" ]]; then
  printf 'refusing to overwrite existing corpus or tools in %s\n' "$workspace" >&2
  exit 73
fi

# 2020-01-01T00:00:00Z. Every corpus file predates this by a wide margin; a
# newer mtime means the extraction discarded the archived timestamps.
MTIME_MAX_EPOCH=1577836800

stage="$(mktemp -d "$workspace/.acquire.XXXXXXXX")"
cleanup() {
  rm -rf -- "$stage"
}
trap cleanup EXIT
install -d -m 0700 "$stage/downloads" "$stage/corpus" "$stage/tools"

download() {
  local url="$1"
  local output="$2"
  curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
    --connect-timeout 30 --max-time 1800 --output "$output" "$url"
}

verify_sha256() {
  local expected="$1"
  local path="$2"
  printf '%s  %s\n' "$expected" "$path" | sha256sum --check --status
}

download https://corpus.canterbury.ac.nz/resources/cantrbry.zip \
  "$stage/downloads/cantrbry.zip"
verify_sha256 c44b686dfc137e74aba4db0540e5d6568cb09e270ba8f8411d2f9df24f39a1a6 \
  "$stage/downloads/cantrbry.zip"
install -d -m 0700 "$stage/corpus/canterbury"
unzip -q "$stage/downloads/cantrbry.zip" -d "$stage/corpus/canterbury"

download https://www.mattmahoney.net/dc/enwik8.zip \
  "$stage/downloads/enwik8.zip"
verify_sha256 547994d9980ebed1288380d652999f38a14fe291a6247c157c3d33d4932534bc \
  "$stage/downloads/enwik8.zip"
install -d -m 0700 "$stage/corpus/enwik8"
unzip -q "$stage/downloads/enwik8.zip" -d "$stage/corpus/enwik8"

download https://sun.aei.polsl.pl/~sdeor/corpus/silesia.zip \
  "$stage/downloads/silesia.zip"
verify_sha256 0626e25f45c0ffb5dc801f13b7c82a3b75743ba07e3a71835a41e3d9f63c77af \
  "$stage/downloads/silesia.zip"
install -d -m 0700 "$stage/corpus/silesia"
unzip -q "$stage/downloads/silesia.zip" -d "$stage/corpus/silesia"

while IFS=$'\t' read -r corpus file _kind size expected_hash; do
  [[ "$corpus" == "corpus" ]] && continue
  path="$stage/corpus/$corpus/$file"
  [[ -f "$path" ]] || { printf 'missing corpus file: %s\n' "$path" >&2; exit 66; }
  [[ "$(stat -c '%s' "$path")" == "$size" ]] \
    || { printf 'size mismatch: %s\n' "$path" >&2; exit 65; }
  verify_sha256 "$expected_hash" "$path" \
    || { printf 'checksum mismatch: %s\n' "$path" >&2; exit 65; }
  # RAR stores each source file's modification time in the archive, and the
  # encoding width depends on how old that time is. Every corpus here is a
  # historical dataset whose archives carry 1990s/2000s timestamps, so if
  # extraction did not restore them the rar archives come out 16 bytes larger
  # per file and verification fails on the rar cells only, with nothing in the
  # message pointing at the cause. Fail here instead, where it is explainable.
  # The exact timestamp does not matter -- a whole-timezone shift still
  # reproduces the published bytes -- only that it was preserved at all.
  mtime_epoch="$(stat -c '%Y' "$path")"
  if (( mtime_epoch > MTIME_MAX_EPOCH )); then
    printf 'corpus timestamps were not preserved: %s has mtime %s\n' \
      "$path" "$(date -u -d "@$mtime_epoch" '+%Y-%m-%d')" >&2
    printf 'extract with a tool that restores stored mtimes (plain `unzip`, not `unzip -DD`);\n' >&2
    printf 'otherwise the rar measurements cannot match the published values.\n' >&2
    exit 65
  fi
done < "$package_root/corpus_manifest.tsv"

download \
  https://github.com/Arcanada-one/cubrim/releases/download/v0.3.2/cubrim-v0.3.2-linux-x86_64.tar.gz \
  "$stage/downloads/cubrim.tar.gz"
verify_sha256 cbf672e15e425032b6b9bcf28c1308650edb9b4de47d6e04a26414a038ed36fe \
  "$stage/downloads/cubrim.tar.gz"
tar -xzf "$stage/downloads/cubrim.tar.gz" -C "$stage" ./cubrim
verify_sha256 b6c3cd251f7148c1895f5b85d30d06df8252a70afbd649e269f673a19e2a5768 \
  "$stage/cubrim"
install -m 0555 "$stage/cubrim" "$stage/tools/cubrim"

download https://www.rarlab.com/rar/rarlinux-x64-700.tar.gz \
  "$stage/downloads/rar.tar.gz"
verify_sha256 1dbbfaf1a9697826ee1c52cfdfa10667ff6713500d96926383a8771b3eeee222 \
  "$stage/downloads/rar.tar.gz"
tar -xzf "$stage/downloads/rar.tar.gz" -C "$stage" \
  rar/rar rar/unrar rar/license.txt
verify_sha256 338274d321513def3891594195ba18aad0c00ef75dc05a94be74e556d8f6c3c0 \
  "$stage/rar/rar"
verify_sha256 5be5875a026a2e5fc41a885ae2ef2484e0e6d5e1c119992e784f993df1c2339d \
  "$stage/rar/unrar"
install -m 0555 "$stage/rar/rar" "$stage/tools/rar"
install -m 0555 "$stage/rar/unrar" "$stage/tools/unrar"
install -m 0444 "$stage/rar/license.txt" "$stage/tools/RAR-LICENSE.txt"

mv -- "$stage/corpus" "$workspace/corpus"
mv -- "$stage/tools" "$workspace/tools"
printf 'Acquisition complete. Read %s before using RAR.\n' \
  "$workspace/tools/RAR-LICENSE.txt"
