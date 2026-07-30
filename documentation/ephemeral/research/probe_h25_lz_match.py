"""
H-25 probe — LZ77 match modeling as a NEW value-stream class (beyond BWT-family).

Why: the holdout re-check (h-robust2) shows Cubrim (cube+BWT+rANS) is ~1.3% behind
gzip and ~8% behind zstd-19 on unseen data, losing 4/6 files. gzip and zstd both
win via LZ dictionary matching (long-range repeats) — a capability Cubrim's pipeline
has NO model for. This is the genuinely-new class: tokenize into (literal, match)
via LZ77, then entropy-code the LITERAL stream with Cubrim's strong BWT+order-k rANS
backend and the length/distance streams with rANS.

This is a CHEAP, charged probe (no Rust): greedy LZ77 (hash-chain, 32KB window,
min-match 3 — gzip-like) on each holdout file, then a Gotcha-#6 charged size model:
  - literal stream: charged at order-0 AND order-1 entropy (the brief's order-1
    entropy probe — it gates the literal coder, the only reorder-able sub-stream);
  - match tokens: charged with a deflate-like model (length + distance extra bits).
Gate: does the charged LZ estimate undercut gzip on the files Cubrim currently loses?
If yes on the loss files -> GO-worthy (implement as a new non-BWT ValueScheme).
If the charged estimate cannot beat gzip -> NO-GO (LZ adds nothing over the 30-year
general compressor), log it. NO tuning to the holdout.
"""

import math
import subprocess
from pathlib import Path

HOLDOUT = Path(__file__).resolve().parent / "holdout"
WINDOW = 32768          # gzip-like 32KB sliding window
MIN_MATCH = 3
MAX_MATCH = 258         # deflate cap
MAX_CHAIN = 256         # hash-chain search depth (bounds cost)


def h0_bits(symbols: list[int]) -> float:
    """Order-0 entropy (bits) of a symbol stream."""
    if not symbols:
        return 0.0
    from collections import Counter
    n = len(symbols)
    c = Counter(symbols)
    return sum(cnt * -math.log2(cnt / n) for cnt in c.values())


def h1_bits(symbols: list[int]) -> float:
    """Order-1 conditional entropy (bits): sum over contexts of H0 within context."""
    if len(symbols) < 2:
        return h0_bits(symbols)
    from collections import defaultdict, Counter
    ctx = defaultdict(Counter)
    for a, b in zip(symbols, symbols[1:]):
        ctx[a][b] += 1
    total = 0.0
    for _, counter in ctx.items():
        n = sum(counter.values())
        total += sum(cnt * -math.log2(cnt / n) for cnt in counter.values())
    return total  # first symbol charged ~0 (negligible)


def lz77_parse(data: bytes):
    """Greedy LZ77 with hash chains. Returns (literals, matches) where matches are
    (length, distance) and literals is the list of literal byte values (in order)."""
    n = len(data)
    head = {}                       # 3-byte key -> most recent position
    prev = [-1] * n                 # chain: prev occurrence of same 3-byte key
    literals: list[int] = []
    matches: list[tuple[int, int]] = []
    # token order is needed for the flag stream; record per-token is_match
    flags: list[int] = []
    i = 0
    while i < n:
        best_len, best_dist = 0, 0
        if i + MIN_MATCH <= n:
            key = data[i:i + 3]
            j = head.get(key, -1)
            chain = 0
            limit = max(0, i - WINDOW)
            while j >= limit and chain < MAX_CHAIN:
                # extend match
                ml = 0
                maxl = min(MAX_MATCH, n - i)
                while ml < maxl and data[j + ml] == data[i + ml]:
                    ml += 1
                if ml > best_len:
                    best_len, best_dist = ml, i - j
                    if ml >= maxl:
                        break
                j = prev[j]
                chain += 1
        if best_len >= MIN_MATCH:
            matches.append((best_len, best_dist))
            flags.append(1)
            # insert hash entries for the matched span (cheap: only step positions)
            end = i + best_len
            while i < end and i + 3 <= n:
                key = data[i:i + 3]
                prev[i] = head.get(key, -1)
                head[key] = i
                i += 1
            i = end
        else:
            literals.append(data[i])
            flags.append(0)
            if i + 3 <= n:
                key = data[i:i + 3]
                prev[i] = head.get(key, -1)
                head[key] = i
            i += 1
    return literals, matches, flags


def match_bits(length: int, distance: int) -> float:
    """Deflate-like charged cost of one match token (excluding the flag bit).
    length: a length code (~5 base bits) + extra bits ~ log2 of the length range.
    distance: a distance code (~5 base bits) + extra bits ~ log2(distance)."""
    len_bits = 5 + max(0, math.log2(max(1, length - MIN_MATCH + 1)))
    dist_bits = 5 + max(0, math.log2(max(1, distance)))
    return len_bits + dist_bits


def gzip_bytes(p: Path) -> int:
    r = subprocess.run(f"gzip -9 -c {p} | wc -c", shell=True,
                       capture_output=True, text=True)
    return int(r.stdout.strip())


def main():
    manifest = sorted(p for p in HOLDOUT.glob("*") if p.name != "manifest.json")
    print(f"{'file':14s} {'size':>7s} {'lits':>7s} {'matches':>8s} "
          f"{'cov%':>6s} {'H0lit':>7s} {'H1lit':>7s} "
          f"{'est_real':>9s} {'est_opt':>8s} {'gzip':>7s}  verdict")
    print("-" * 104)
    for p in manifest:
        data = p.read_bytes()
        n = len(data)
        lits, matches, flags = lz77_parse(data)
        matched_bytes = sum(m[0] for m in matches)
        cov = 100.0 * matched_bytes / n if n else 0.0
        # flag stream entropy (is-match per token)
        flag_bits = h0_bits(flags)
        # literal coder: order-0 and order-1 (BWT+order-1 rANS would approach H1)
        h0 = h0_bits(lits)
        h1 = h1_bits(lits)
        match_total = sum(match_bits(l, d) for (l, d) in matches)
        # realistic: literals at H1 (Cubrim's order-1 backend) + matches + flags
        est_real_bits = h1 + match_total + flag_bits
        # optimistic floor: literals at H1, matches at pure log2(dist)+log2(len)
        opt_match = sum(math.log2(max(1, d)) + math.log2(max(1, l))
                        for (l, d) in matches)
        est_opt_bits = h1 + opt_match + flag_bits
        est_real = math.ceil(est_real_bits / 8)
        est_opt = math.ceil(est_opt_bits / 8)
        gz = gzip_bytes(p)
        verdict = "BEAT-gzip" if est_real < gz else (
            "opt<gzip" if est_opt < gz else "NO")
        print(f"{p.name:14s} {n:>7d} {len(lits):>7d} {len(matches):>8d} "
              f"{cov:>6.1f} {h0/max(1,len(lits)):>7.3f} {h1/max(1,len(lits)):>7.3f} "
              f"{est_real:>9d} {est_opt:>8d} {gz:>7d}  {verdict}")


if __name__ == "__main__":
    main()
