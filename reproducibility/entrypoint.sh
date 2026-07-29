#!/usr/bin/env bash
set -euo pipefail

stage="${1:-}"
if [[ -n "$stage" ]]; then
  shift
fi
case "$stage" in
  acquire)
    exec /opt/cubr-repro/acquire.sh /workspace "$@"
    ;;
  run)
    # Cubrim asks for licence acceptance on first use and records it under
    # $HOME. A container has no TTY and an ephemeral $HOME, so the prompt fails
    # its stdin read and the tool exits 3 on the first Cubrim cell -- with the
    # prompt buried in captured output, that reads as a mysterious encode
    # failure. Acceptance is a legal act, so it is not performed on the
    # operator's behalf: the run refuses to start until it is given explicitly,
    # the same way this package refuses to accept the RAR terms for anyone.
    if [[ "${CUBRIM_ACCEPT_LICENSE:-}" != "1" ]]; then
      printf 'Cubrim requires licence acceptance before it will run.\n\n' >&2
      /workspace/tools/cubrim --license >&2 || true
      printf '\nRe-run with -e CUBRIM_ACCEPT_LICENSE=1 to accept these terms.\n' >&2
      printf 'Note: licence and release fetches log an install id, IP address,\n' >&2
      printf 'OS, architecture, and version to the vendor.\n' >&2
      exit 77
    fi
    /workspace/tools/cubrim --accept-license >/dev/null
    exec python3 /opt/cubr-repro/run_benchmark.py --workspace /workspace "$@"
    ;;
  verify)
    exec python3 /opt/cubr-repro/verify.py --workspace /workspace "$@"
    ;;
  *)
    printf 'usage: docker run ... IMAGE {acquire|run|verify}\n' >&2
    exit 64
    ;;
esac
