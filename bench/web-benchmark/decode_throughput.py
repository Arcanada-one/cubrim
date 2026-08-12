"""In-process decode throughput, because the subprocess protocol cannot measure it.

CUBR-0074 Phase B measured `decode_throughput_vs_brotli5 = 0.9764` against a
0.50 bar and the number meant nothing. The five-metric protocol times a
subprocess per trial; at 10-320 KB every codec sits on a 3.5-4.1 ms floor of
process spawn plus sandbox with the decode work a sliver inside it, so every
ratio is dragged toward 1.0 and a decoder ten times slower would also have
"passed". A 33x increase in content moved the measured time by about 1 ms.

This module removes the floor rather than trying to subtract it: each decoder is
called in-process, warmed up, then timed over N repeats. What is compared is the
decoder, which is what the gate is about — decoding is on the browser critical
path, so the question is how fast the code runs, not how fast Linux forks.

Provenance is preserved, not traded away. The incumbents are timed through the
very shared libraries their pinned CLIs wrap, at matching versions
(libbrotlidec 1.1.0, libzstd 1.5.5), and each library's path, size and SHA-256
are recorded. Cubrim-Web is timed through `cbr_decode` — the same C ABI the
browser calls — so the number describes the artefact that actually ships rather
than an inlined Rust call the deployed decoder never takes.

Every timed iteration verifies its output byte-for-byte against the original. An
iteration without that check is not an observation.

Usage:
    python3 decode_throughput.py --manifest ../web-corpus/manifest.v3.json \\
        --cubrim-lib ../../code/cubrim-web-decoder/target/release/libcubrim_web_decoder.so
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import random
import statistics
import subprocess
import time
import zlib
from pathlib import Path

BROTLI_DECODER_RESULT_SUCCESS = 1
DEFAULT_REPEATS = 30
DEFAULT_WARMUPS = 5
DEFAULT_ROUNDS = 5


def host_admission() -> dict[str, object]:
    """Load and temperature, recorded so a number can be judged, not just read.

    The subprocess harness refuses to run above 1.0 load per CPU. This module
    records rather than refuses, because it is also legitimate to characterise a
    decoder on a busy host as long as the conditions travel with the figure —
    but a report without them is not interpretable.
    """
    import os

    load1 = os.getloadavg()[0]
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else 0
    temps = []
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            temps.append(int(zone.read_text(encoding="ascii").strip()) / 1000)
        except (OSError, ValueError):
            pass
    return {
        "load_1m": load1,
        "cpus": cpus,
        "load_per_cpu": (load1 / cpus) if cpus else None,
        "quiet_ceiling_load_per_cpu": 1.0,
        "within_quiet_ceiling": bool(cpus) and (load1 / cpus) <= 1.0,
        "max_temperature_c": max(temps) if temps else None,
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def library_provenance(path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


class BrotliDecoder:
    """libbrotlidec — the same library the pinned `brotli` CLI wraps."""

    name = "brotli"

    def __init__(self, soname: str = "libbrotlidec.so.1"):
        self.lib = ctypes.CDLL(soname)
        self.path = Path(_resolve_soname(soname))
        fn = self.lib.BrotliDecoderDecompress
        fn.restype = ctypes.c_int
        fn.argtypes = [
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        self.fn = fn

    def prepare(self, frame: bytes, original_len: int):
        src = (ctypes.c_ubyte * len(frame)).from_buffer_copy(frame)
        dst = (ctypes.c_ubyte * original_len)()
        size = ctypes.c_size_t(original_len)
        return src, dst, size

    def decode(self, state) -> None:
        src, dst, size = state
        size.value = len(dst)
        rc = self.fn(len(src), src, ctypes.byref(size), dst)
        if rc != BROTLI_DECODER_RESULT_SUCCESS:
            raise RuntimeError(f"brotli decode failed: {rc}")

    def materialize(self, state) -> bytes:
        _, dst, size = state
        return ctypes.string_at(ctypes.addressof(dst), size.value)


class ZstdDecoder:
    """libzstd — the same library the pinned `zstd` CLI wraps."""

    name = "zstd"

    def __init__(self, soname: str = "libzstd.so.1"):
        self.lib = ctypes.CDLL(soname)
        self.path = Path(_resolve_soname(soname))
        self.lib.ZSTD_decompress.restype = ctypes.c_size_t
        self.lib.ZSTD_decompress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        self.lib.ZSTD_isError.restype = ctypes.c_uint
        self.lib.ZSTD_isError.argtypes = [ctypes.c_size_t]

    def prepare(self, frame: bytes, original_len: int):
        src = ctypes.create_string_buffer(frame, len(frame))
        dst = ctypes.create_string_buffer(original_len)
        return [src, dst, len(frame), [0]]

    def decode(self, state) -> None:
        src, dst, src_len, _ = state
        written = self.lib.ZSTD_decompress(dst, len(dst), src, src_len)
        if self.lib.ZSTD_isError(written):
            raise RuntimeError("zstd decode failed")
        state[3][0] = written

    def materialize(self, state) -> bytes:
        _, dst, _, written = state
        return ctypes.string_at(ctypes.addressof(dst), written[0])


class ZlibDecoder:
    """zlib's inflate.

    Reported for context only, and labelled as zlib rather than gzip: the gzip
    CLI carries its own inflate, so this is not the same implementation the
    gzip-9 column of the subprocess bundle measured. The gate is against
    brotli-5, so nothing depends on this row.
    """

    name = "zlib"

    def __init__(self):
        self.path = None

    def prepare(self, frame: bytes, original_len: int):
        return frame

    def decode(self, state) -> None:
        self._out = zlib.decompress(state, 31)

    def materialize(self, state) -> bytes:
        return self._out


class CubrimWebDecoder:
    """The reference decoder, through the C ABI the browser calls."""

    name = "cubrim-web"

    def __init__(self, library: Path):
        self.lib = ctypes.CDLL(str(library))
        self.path = library
        self.lib.cbr_alloc.restype = ctypes.c_void_p
        self.lib.cbr_alloc.argtypes = [ctypes.c_size_t]
        self.lib.cbr_free.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self.lib.cbr_decode.restype = ctypes.c_uint
        self.lib.cbr_decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
        self.lib.cbr_out_ptr.restype = ctypes.c_void_p
        self.lib.cbr_out_len.restype = ctypes.c_size_t

    def prepare(self, frame: bytes, original_len: int):
        ptr = self.lib.cbr_alloc(len(frame))
        if not ptr:
            raise RuntimeError("cbr_alloc returned NULL")
        ctypes.memmove(ptr, frame, len(frame))
        return ptr, len(frame), original_len

    def release(self, state) -> None:
        ptr, length, _ = state
        self.lib.cbr_free(ptr, length)

    def decode(self, state) -> None:
        # No `cbr_out_clear()` here: it calls `shrink_to_fit`, and timing a
        # deallocation that is not part of decoding would handicap the candidate
        # against incumbents that write into a caller-provided buffer.
        # `cbr_decode` replaces the output slot wholesale, so the clear is not
        # needed for correctness either.
        ptr, length, original_len = state
        handle = self.lib.cbr_decode(ptr, length, max(original_len * 2, 1 << 16))
        if handle == 0:
            raise RuntimeError("cbr_decode rejected the frame")

    def materialize(self, state) -> bytes:
        return ctypes.string_at(self.lib.cbr_out_ptr(), self.lib.cbr_out_len())


def _resolve_soname(soname: str) -> str:
    """Where the loader actually found the library — recorded, not assumed."""
    out = subprocess.run(
        ("/sbin/ldconfig", "-p"), stdout=subprocess.PIPE, text=True, check=False, timeout=20
    ).stdout
    for line in out.splitlines():
        if soname in line and "=>" in line:
            return line.split("=>")[-1].strip()
    return soname


def time_decoder(decoder, frame: bytes, original: bytes, *, repeats: int, warmups: int):
    """Time the decode call alone; verify the output outside the clock.

    The first version of this timed `decode()` *and* the conversion of its
    output into Python bytes, and reported Cubrim-Web at 10.4x brotli-5 —
    because `bytes(ctypes_array[:n])` marshals element by element while
    `string_at` is a memcpy. It was measuring the binding, not the decoder.
    Marshalling now happens after the clock stops, and correctness is still
    checked on every iteration rather than once.
    """
    state = decoder.prepare(frame, len(original))
    try:
        for _ in range(warmups):
            decoder.decode(state)
            if decoder.materialize(state) != original:
                raise RuntimeError(f"{decoder.name}: warm-up output is not byte-exact")
        samples = []
        for _ in range(repeats):
            start = time.perf_counter_ns()
            decoder.decode(state)
            elapsed = time.perf_counter_ns() - start
            if decoder.materialize(state) != original:
                raise RuntimeError(f"{decoder.name}: timed output is not byte-exact")
            samples.append(elapsed)
        return samples
    finally:
        release = getattr(decoder, "release", None)
        if release is not None:
            release(state)


def compress(argv: tuple[str, ...], path: Path) -> bytes:
    result = subprocess.run(
        argv + (str(path),), stdout=subprocess.PIPE, check=True, timeout=300
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cubrim-lib", type=Path, required=True)
    parser.add_argument("--cubrim-web", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--seed", type=int, default=74074)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.parent

    codecs = {
        "brotli-11": (("brotli", "--quality=11", "--stdout"), BrotliDecoder()),
        "brotli-5": (("brotli", "--quality=5", "--stdout"), BrotliDecoder()),
        "zstd-19": (("zstd", "-19", "--quiet", "--stdout"), ZstdDecoder()),
        "zstd-3": (("zstd", "-3", "--quiet", "--stdout"), ZstdDecoder()),
        "gzip-9": (("gzip", "-9", "-c"), ZlibDecoder()),
        "cubrim-web": (
            (str(args.cubrim_web), "encode"),
            CubrimWebDecoder(args.cubrim_lib),
        ),
    }

    # Compress once. Compression is not being timed here, and re-running it per
    # round would only add noise to the thing that is.
    cells = []
    for name, (argv, decoder) in codecs.items():
        for sample in manifest["samples"]:
            source = root / sample["path"]
            original = source.read_bytes()
            cells.append(
                {
                    "codec": name,
                    "decoder": decoder,
                    "sample_id": sample["sample_id"],
                    "original": original,
                    "frame": compress(argv, source),
                    "observations": [],
                }
            )

    admission_before = host_admission()
    # Rounds in a seeded random order, per-cell minimum kept across rounds.
    # Measuring every cell of codec A and then every cell of codec B would let a
    # load change land entirely on one codec; the subprocess harness randomizes
    # its schedule for the same reason, and the native decode bench takes the
    # minimum across rounds as the least contaminated observation.
    rng = random.Random(args.seed)
    for _ in range(args.rounds):
        order = list(range(len(cells)))
        rng.shuffle(order)
        for index in order:
            cell = cells[index]
            cell["observations"].extend(
                time_decoder(
                    cell["decoder"],
                    cell["frame"],
                    cell["original"],
                    repeats=args.repeats,
                    warmups=args.warmups,
                )
            )
    admission_after = host_admission()

    results: dict[str, dict[str, object]] = {}
    for name, (_, decoder) in codecs.items():
        per_sample = [
            {
                "sample_id": c["sample_id"],
                "original_bytes": len(c["original"]),
                "compressed_bytes": len(c["frame"]),
                "min_ns": min(c["observations"]),
                "median_ns": statistics.median(c["observations"]),
                "observations": len(c["observations"]),
            }
            for c in cells
            if c["codec"] == name
        ]
        total_bytes = sum(s["original_bytes"] for s in per_sample)
        total_min_ns = sum(s["min_ns"] for s in per_sample)
        total_median_ns = sum(s["median_ns"] for s in per_sample)
        results[name] = {
            "library": library_provenance(decoder.path) if decoder.path else None,
            "samples": per_sample,
            "total_original_bytes": total_bytes,
            "mb_per_s_min": total_bytes / (total_min_ns / 1e9) / 1e6,
            "mb_per_s_median": total_bytes / (total_median_ns / 1e9) / 1e6,
        }

    # The gate is read off the MINIMUM, the least contaminated observation of
    # each cell. The median is reported beside it so the two can be compared:
    # if they disagree materially, the host was too noisy to conclude from.
    ratio_min = results["cubrim-web"]["mb_per_s_min"] / results["brotli-5"]["mb_per_s_min"]
    ratio_median = (
        results["cubrim-web"]["mb_per_s_median"] / results["brotli-5"]["mb_per_s_median"]
    )
    report = {
        "schema_version": 1,
        "scope": "decode_throughput_in_process",
        "method": (
            "in-process decode; compress once, then N rounds over a seeded "
            "randomized cell order, warm-up plus R repeats per visit, output "
            "verified byte-exact on every timed iteration; per-cell minimum kept"
        ),
        "repeats_per_visit": args.repeats,
        "warmups_per_visit": args.warmups,
        "rounds": args.rounds,
        "seed": args.seed,
        "admission_before": admission_before,
        "admission_after": admission_after,
        "corpus": {
            "manifest_name": args.manifest.name,
            "manifest_sha256": sha256_file(args.manifest),
            "sample_count": len(manifest["samples"]),
        },
        "codecs": results,
        "gate": {
            "criterion": "decode_throughput_vs_brotli5",
            "bar": 0.50,
            "value_from_min": ratio_min,
            "value_from_median": ratio_median,
            "passes": ratio_min >= 0.50,
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
