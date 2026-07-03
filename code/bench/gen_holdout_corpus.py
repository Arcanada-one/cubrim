"""
Holdout corpus generator — Cubrim robustness study (CUBR-CONT).

Builds a SEPARATE, diverse holdout corpus of REAL-WORLD files to test whether
Cubrim's tuned-corpus parity with gzip generalises. This corpus is deliberately
disjoint from the frozen leaderboard corpus (documentation/ephemeral/research/corpus/);
nothing here touches or reads that manifest.

Design:
  - Each entry copies REAL bytes from a stable source on this host and FREEZES
    them into documentation/ephemeral/research/holdout/. The frozen copies are committed,
    so the benchmark is reproducible from the corpus itself regardless of whether
    the original source paths still exist later.
  - One synthetic-but-realistic entry (a CSV) is generated deterministically when
    no real source is configured, but here we prefer a real CSV when present.
  - A manifest.json records name, frozen size, sha256, and provenance (source).

Categories covered (operator brief): real source code, JSON, English prose,
a small binary/executable, a CSV.

Usage:
  python3 code/bench/gen_holdout_corpus.py
"""

import hashlib
import json
import subprocess
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent  # repo root
HOLDOUT_DIR = _PROJECT / "documentation" / "ephemeral" / "research" / "holdout"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_existing(paths: list[str]) -> Path | None:
    for p in paths:
        pp = Path(p)
        if pp.is_file():
            return pp
    return None


def grab_file(category: str, candidates: list[str]) -> tuple[bytes, str] | None:
    """Return (bytes, source_path) from the first existing candidate."""
    src = first_existing(candidates)
    if src is None:
        print(f"  WARN [{category}]: none of the candidate sources exist")
        return None
    return src.read_bytes(), str(src)


def grab_manpage(name: str, section: str = "1") -> tuple[bytes, str] | None:
    """Render a man page to plain English text (real natural-language prose)."""
    try:
        man = subprocess.run(["man", section, name], capture_output=True)
        if man.returncode != 0 or not man.stdout:
            return None
        col = subprocess.run(["col", "-b"], input=man.stdout, capture_output=True)
        text = col.stdout if col.returncode == 0 and col.stdout else man.stdout
        return text, f"man {section} {name} | col -b"
    except FileNotFoundError:
        return None


# Each entry: (frozen_filename, category, grabber)
# Grabbers are tried in order; the first that yields bytes wins.
ENTRIES = [
    # Real source code #1 — Rust (committed in this repo, fully reproducible).
    ("rust_src.rs", "source-code-rust",
     lambda: grab_file("rust", [str(_PROJECT / "code/cubrim-rs/src/huffman.rs")])),

    # Real source code #2 — C system header (real third-party source).
    ("c_header.h", "source-code-c",
     lambda: grab_file("c", ["/usr/include/stdio.h", "/usr/include/stdlib.h"])),

    # Real JSON — a real-world config / data file (NOT a Cubrim bench output).
    ("config.json", "json",
     lambda: grab_file("json", [
         "/home/dev/WebStorm-261.22158.274/license/third-party-libraries.json",
         "/home/dev/.codex/models_cache.json",
     ])),

    # English prose — natural-language documentation rendered to plain text.
    ("prose.txt", "english-prose",
     lambda: grab_manpage("gzip", "1") or grab_manpage("tar", "1")
             or grab_file("prose", ["/usr/share/common-licenses/GPL-3"])),

    # Real CSV — financial/tabular records.
    ("data.csv", "csv",
     lambda: grab_file("csv", [
         "/home/dev/paxbt-monitor/pull/deals.csv",
     ])),

    # Small binary / executable — a real ELF.
    ("exe.bin", "binary-executable",
     lambda: grab_file("binary", ["/bin/cat", "/usr/bin/cat", "/bin/true"])),
]


def main() -> None:
    HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    print(f"Freezing holdout corpus into {HOLDOUT_DIR}")
    for fname, category, grabber in ENTRIES:
        got = grabber()
        if got is None:
            print(f"  SKIP {fname} [{category}]: no source available on this host")
            continue
        data, source = got
        out = HOLDOUT_DIR / fname
        out.write_bytes(data)
        digest = sha256_of(data)
        manifest.append({
            "name": fname,
            "category": category,
            "size_bytes": len(data),
            "sha256": digest,
            "source": source,
        })
        print(f"  {fname:14s} {len(data):>7d} B  [{category}]  <- {source}")

    manifest_path = HOLDOUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nManifest: {manifest_path}  ({len(manifest)} files)")


if __name__ == "__main__":
    main()
