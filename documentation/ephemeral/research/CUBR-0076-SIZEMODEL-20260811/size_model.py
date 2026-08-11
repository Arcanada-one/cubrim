#!/usr/bin/env python3
"""CUBR-0076 charged size model for the table-driven (static-table) web scheme.

Paper spike, step 1 of CUBR-0076-PROTOTYPE-SHAPE-20260806.md, under the
decision rule frozen in CUBR-0076-SIZEMODEL-PREREG-20260811.md.

Charges one cost term per decoder branch, static tables in the header
INCLUDED. Produces bytes only -- no timing claim of any kind, no DB write.

Every reported size is the sum of its itemised branch charges (asserted), and
every token stream is proven to reconstruct its input byte-exactly before any
size is reported.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Wire-format constants (the shape being charged)
# --------------------------------------------------------------------------

MIN_MATCH = 3
MAX_MATCH = 258

# Frame header, bytes: magic(4) + version(1) + scheme(1) + flags(1).
FRAME_FIXED_BYTES = 7
CHECKSUM_BYTES = 4

# Per-block header bits: final-block flag(1) + block type(2).
BLOCK_HEADER_BITS = 3

# Alphabet-size fields in the block header, bits.
HLIT_BITS = 5   # number of literal/length codes used, 257..288
HDIST_BITS = 6  # 6 not 5: the extended distance alphabet exceeds 32 codes
HCLEN_BITS = 4  # number of code-length-code lengths present

MAX_CODE_LEN = 15       # length limit for the literal/length and distance codes
MAX_CL_CODE_LEN = 7     # length limit for the code-length alphabet

# Code-length alphabet: 0..15 literal lengths, 16 = repeat previous 3-6
# (2 extra bits), 17 = repeat zero 3-10 (3 extra), 18 = repeat zero 11-138
# (7 extra). Transmission order is deflate's.
CL_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]
CL_ALPHABET = 19

# Length codes: deflate's 29 codes, symbol 257..285.
LENGTH_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35,
               43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LENGTH_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
                4, 4, 4, 4, 5, 5, 5, 5, 0]
N_LENGTH_CODES = len(LENGTH_BASE)
LITLEN_ALPHABET = 256 + 1 + N_LENGTH_CODES  # literals + EOB + length codes
EOB_SYMBOL = 256


def _build_distance_tables(max_window: int) -> tuple[list[int], list[int]]:
    """Deflate distance codes, extended by doubling past 32 KiB.

    Codes 0..3 are distances 1..4 with no extra bits; every later pair of codes
    doubles the covered range and adds one extra bit. Extending the same rule
    past deflate's 30 codes is what buys the whole-file window.
    """
    base = [1, 2, 3, 4]
    extra = [0, 0, 0, 0]
    nxt = 5
    bits = 1
    while base[-1] + (1 << extra[-1]) - 1 < max_window:
        for _ in range(2):
            base.append(nxt)
            extra.append(bits)
            nxt += 1 << bits
        bits += 1
    return base, extra


DIST_BASE, DIST_EXTRA = _build_distance_tables(1 << 22)
N_DIST_CODES = len(DIST_BASE)


def length_code(length: int) -> int:
    """Index into LENGTH_BASE for a match length."""
    assert MIN_MATCH <= length <= MAX_MATCH, length
    lo, hi = 0, N_LENGTH_CODES - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if LENGTH_BASE[mid] <= length:
            lo = mid
        else:
            hi = mid - 1
    return lo


def dist_code(distance: int) -> int:
    """Index into DIST_BASE for a match distance."""
    assert distance >= 1, distance
    lo, hi = 0, N_DIST_CODES - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if DIST_BASE[mid] <= distance:
            lo = mid
        else:
            hi = mid - 1
    return lo


# --------------------------------------------------------------------------
# Length-limited canonical Huffman (package-merge)
# --------------------------------------------------------------------------

def huffman_lengths(freqs: list[int], limit: int) -> list[int]:
    """Optimal code lengths under a maximum-length limit.

    Plain Huffman first; package-merge (Larmore-Hirschberg) only when the
    unconstrained code violates the limit. Symbols with zero frequency get
    length 0 and are not transmitted as codes.
    """
    used = [(f, i) for i, f in enumerate(freqs) if f > 0]
    lengths = [0] * len(freqs)
    if not used:
        return lengths
    if len(used) == 1:
        lengths[used[0][1]] = 1  # a lone symbol still costs one bit
        return lengths

    plain = _plain_huffman(used, len(freqs))
    if max(plain) <= limit:
        return plain
    return _package_merge(used, len(freqs), limit)


def _plain_huffman(used: list[tuple[int, int]], n: int) -> list[int]:
    heap: list[tuple[int, int, object]] = []
    for order, (f, sym) in enumerate(used):
        heap.append((f, order, (sym,)))
    heapq.heapify(heap)
    counter = len(used)
    depth: dict[int, int] = {sym: 0 for _, sym in used}
    while len(heap) > 1:
        f1, _, g1 = heapq.heappop(heap)
        f2, _, g2 = heapq.heappop(heap)
        for sym in g1:
            depth[sym] += 1
        for sym in g2:
            depth[sym] += 1
        heapq.heappush(heap, (f1 + f2, counter, tuple(g1) + tuple(g2)))
        counter += 1
    lengths = [0] * n
    for sym, d in depth.items():
        lengths[sym] = d
    return lengths


def _package_merge(used: list[tuple[int, int]], n: int, limit: int) -> list[int]:
    items = sorted(used)  # (freq, symbol)
    k = len(items)
    assert (1 << limit) >= k, "limit too small for alphabet"
    # Each list level holds packages; a package is (weight, [symbol indices]).
    base = [(f, [i]) for i, (f, _) in enumerate(items)]
    current = list(base)
    for _ in range(limit - 1):
        packages = []
        for j in range(0, len(current) - 1, 2):
            w = current[j][0] + current[j + 1][0]
            packages.append((w, current[j][1] + current[j + 1][1]))
        current = sorted(base + packages)
    counts = [0] * k
    for _, members in current[: 2 * k - 2]:
        for idx in members:
            counts[idx] += 1
    lengths = [0] * n
    for idx, (_, sym) in enumerate(items):
        lengths[sym] = counts[idx]
    return lengths


def kraft_sum(lengths: list[int]) -> float:
    return sum(2.0 ** -length for length in lengths if length > 0)


# --------------------------------------------------------------------------
# LZ parse (hash-chain, lazy) -- the parse-quality axis
# --------------------------------------------------------------------------

@dataclass
class Token:
    """A literal (length 0) or a match."""
    literal: int = -1
    length: int = 0
    distance: int = 0


def lz_parse(data: bytes, window: int, max_chain: int, lazy: bool = True,
             nice_length: int = 128) -> list[Token]:
    """Hash-chain lazy matcher. Deeper chains = better parse quality."""
    n = len(data)
    tokens: list[Token] = []
    if n == 0:
        return tokens
    head: dict[int, int] = {}
    prev = [-1] * n

    def insert(pos: int) -> None:
        if pos + MIN_MATCH > n:
            return
        h = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
        prev[pos] = head.get(h, -1)
        head[h] = pos

    def longest(pos: int, limit_chain: int) -> tuple[int, int]:
        if pos + MIN_MATCH > n:
            return 0, 0
        h = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
        cand = head.get(h, -1)
        best_len, best_dist = 0, 0
        max_len = min(MAX_MATCH, n - pos)
        chain = limit_chain
        while cand >= 0 and chain > 0:
            dist = pos - cand
            if dist > window:
                break
            # cheap reject on the byte that would extend the current best
            if best_len == 0 or data[cand + best_len] == data[pos + best_len]:
                length = 0
                while (length < max_len
                       and data[cand + length] == data[pos + length]):
                    length += 1
                if length > best_len:
                    best_len, best_dist = length, dist
                    if length >= nice_length or length == max_len:
                        break
            cand = prev[cand]
            chain -= 1
        if best_len < MIN_MATCH:
            return 0, 0
        return best_len, best_dist

    i = 0
    while i < n:
        cur_len, cur_dist = longest(i, max_chain)
        if lazy and cur_len >= MIN_MATCH and cur_len < nice_length and i + 1 < n:
            insert(i)
            nxt_len, nxt_dist = longest(i + 1, max_chain)
            if nxt_len > cur_len:
                tokens.append(Token(literal=data[i]))
                i += 1
                cur_len, cur_dist = nxt_len, nxt_dist
                insert(i)
            for j in range(i + 1, i + cur_len):
                insert(j)
            tokens.append(Token(length=cur_len, distance=cur_dist))
            i += cur_len
        elif cur_len >= MIN_MATCH:
            for j in range(i, i + cur_len):
                insert(j)
            tokens.append(Token(length=cur_len, distance=cur_dist))
            i += cur_len
        else:
            insert(i)
            tokens.append(Token(literal=data[i]))
            i += 1
    return tokens


def collect_candidates(data: bytes, window: int, max_chain: int,
                       length_cap: int = MAX_MATCH) -> list[list[tuple[int, int]]]:
    """Per position, the improving (length, distance) pairs found on the chain.

    A pair (L, d) means: every match length in (previous recorded L, L] is
    available at distance d. This is the candidate set the optimal parse
    searches over.
    """
    n = len(data)
    head: dict[int, int] = {}
    prev = [-1] * n
    out: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for pos in range(n):
        if pos + MIN_MATCH <= n:
            h = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
            cand = head.get(h, -1)
            best_len = 0
            max_len = min(length_cap, n - pos)
            chain = max_chain
            found = out[pos]
            while cand >= 0 and chain > 0:
                dist = pos - cand
                if dist > window:
                    break
                if best_len == 0 or data[cand + best_len] == data[pos + best_len]:
                    length = 0
                    while (length < max_len
                           and data[cand + length] == data[pos + length]):
                        length += 1
                    if length > best_len and length >= MIN_MATCH:
                        best_len = length
                        found.append((length, dist))
                        if length == max_len:
                            break
                cand = prev[cand]
                chain -= 1
            prev[pos] = head.get(h, -1)
            head[h] = pos
    return out


def _symbol_prices(tokens: list[Token]) -> tuple[list[int], list[int]]:
    """Bit prices per symbol, from a parse's own histogram.

    Unused symbols are priced just above the code-length limit rather than
    excluded, so the optimal parse may still reach for them.
    """
    litlen_freqs = [0] * LITLEN_ALPHABET
    dist_freqs = [0] * N_DIST_CODES
    for tok in tokens:
        if tok.length == 0:
            litlen_freqs[tok.literal] += 1
        else:
            litlen_freqs[256 + 1 + length_code(tok.length)] += 1
            dist_freqs[dist_code(tok.distance)] += 1
    litlen_freqs[EOB_SYMBOL] += 1
    litlen = huffman_lengths(litlen_freqs, MAX_CODE_LEN)
    dist = huffman_lengths(dist_freqs, MAX_CODE_LEN)
    unused = MAX_CODE_LEN + 1
    return ([length or unused for length in litlen],
            [length or unused for length in dist])


def lz_parse_optimal(data: bytes, window: int, max_chain: int,
                     iterations: int = 3, length_cap: int = 258,
                     explore: int = 32) -> list[Token]:
    """Shortest-path (zopfli-class) parse against a real bit-price table.

    Public, long-standing encoder technique -- no new heuristic is invented
    here. It exists to settle whether a shortfall is a property of the scheme
    or of the parser, which the conservative-parse rule requires before any
    NO-GO can be stated.
    """
    n = len(data)
    if n == 0:
        return []
    candidates = collect_candidates(data, window, max_chain, length_cap)
    tokens = lz_parse(data, window=window, max_chain=max_chain)
    for _ in range(iterations):
        lit_price, dist_price = _symbol_prices(tokens)
        cost = [0] * (n + 1)
        choice: list[tuple[int, int]] = [(0, 0)] * (n + 1)
        for i in range(n - 1, -1, -1):
            best_cost = lit_price[data[i]] + cost[i + 1]
            best_choice = (0, 0)
            floor_len = MIN_MATCH - 1
            for length, dist in candidates[i]:
                dc = dist_price[dist_code(dist)] + DIST_EXTRA[dist_code(dist)]
                # every length in (floor_len, length] is reachable at `dist`
                lows = range(floor_len + 1, min(length, explore) + 1)
                for probe in list(lows) + ([length] if length > explore else []):
                    lc = length_code(probe)
                    price = (lit_price[256 + 1 + lc] + LENGTH_EXTRA[lc] + dc
                             + cost[i + probe])
                    if price < best_cost:
                        best_cost = price
                        best_choice = (probe, dist)
                floor_len = length
            cost[i] = best_cost
            choice[i] = best_choice
        tokens = []
        i = 0
        while i < n:
            length, dist = choice[i]
            if length == 0:
                tokens.append(Token(literal=data[i]))
                i += 1
            else:
                tokens.append(Token(length=length, distance=dist))
                i += length
    return tokens


def reconstruct(tokens: list[Token]) -> bytes:
    """Rebuild the input from the token stream alone (the soundness gate)."""
    out = bytearray()
    for tok in tokens:
        if tok.length == 0:
            out.append(tok.literal)
        else:
            start = len(out) - tok.distance
            assert start >= 0, "distance runs before the start of the stream"
            for k in range(tok.length):
                out.append(out[start + k])
    return bytes(out)


# --------------------------------------------------------------------------
# Charged cost accounting
# --------------------------------------------------------------------------

@dataclass
class Charge:
    """Itemised per-decoder-branch charge, in bits."""
    frame_header: int = 0
    block_headers: int = 0
    table_descriptors: int = 0
    literals: int = 0
    lengths: int = 0
    length_extra: int = 0
    distances: int = 0
    distance_extra: int = 0
    eob: int = 0
    checksum: int = 0
    context_map: int = 0
    notes: dict = field(default_factory=dict)

    def total_bits(self) -> int:
        return (self.frame_header + self.block_headers + self.table_descriptors
                + self.literals + self.lengths + self.length_extra
                + self.distances + self.distance_extra + self.eob
                + self.checksum + self.context_map)

    def total_bytes(self) -> int:
        # one byte-alignment pad at end of stream, charged
        return (self.total_bits() + 7) // 8

    def items(self) -> dict:
        return {
            "frame_header": self.frame_header,
            "block_headers": self.block_headers,
            "table_descriptors": self.table_descriptors,
            "literals": self.literals,
            "lengths": self.lengths,
            "length_extra": self.length_extra,
            "distances": self.distances,
            "distance_extra": self.distance_extra,
            "eob": self.eob,
            "checksum": self.checksum,
            "context_map": self.context_map,
        }

    def add(self, other: "Charge") -> None:
        self.frame_header += other.frame_header
        self.block_headers += other.block_headers
        self.table_descriptors += other.table_descriptors
        self.literals += other.literals
        self.lengths += other.lengths
        self.length_extra += other.length_extra
        self.distances += other.distances
        self.distance_extra += other.distance_extra
        self.eob += other.eob
        self.checksum += other.checksum
        self.context_map += other.context_map


def varint_bits(value: int) -> int:
    """LEB128, charged in bits."""
    bits = 8
    while value >= 128:
        value >>= 7
        bits += 8
    return bits


def rle_code_lengths(lengths: list[int]) -> list[tuple[int, int, int]]:
    """Deflate's RLE over a code-length sequence.

    Returns (symbol, extra_bits, extra_value) triples for the code-length
    alphabet: 16 repeat-previous 3-6, 17 repeat-zero 3-10, 18 repeat-zero
    11-138.
    """
    out: list[tuple[int, int, int]] = []
    i = 0
    n = len(lengths)
    while i < n:
        cur = lengths[i]
        run = 1
        while i + run < n and lengths[i + run] == cur:
            run += 1
        if cur == 0:
            while run >= 11:
                take = min(run, 138)
                out.append((18, 7, take - 11))
                run -= take
                i += take
            while run >= 3:
                take = min(run, 10)
                out.append((17, 3, take - 3))
                run -= take
                i += take
            for _ in range(run):
                out.append((0, 0, 0))
                i += 1
        else:
            out.append((cur, 0, 0))
            i += 1
            run -= 1
            while run >= 3:
                take = min(run, 6)
                out.append((16, 2, take - 3))
                run -= take
                i += take
            for _ in range(run):
                out.append((cur, 0, 0))
                i += 1
    return out


def table_descriptor_bits(*alphabets: list[int]) -> tuple[int, dict]:
    """Charge for transmitting the code lengths of every alphabet in a block.

    This is branch 3: the static tables on the wire. Charged exactly as a
    decoder would read them -- alphabet-size fields, the code-length
    alphabet's own lengths, then the RLE-coded, Huffman-coded length
    sequences.
    """
    seq: list[int] = []
    for lengths in alphabets:
        used = len(lengths)
        while used > 1 and lengths[used - 1] == 0:
            used -= 1
        seq.extend(lengths[:used])
    rle = rle_code_lengths(seq)
    cl_freqs = [0] * CL_ALPHABET
    for sym, _, _ in rle:
        cl_freqs[sym] += 1
    cl_lengths = huffman_lengths(cl_freqs, MAX_CL_CODE_LEN)

    hclen = CL_ALPHABET
    while hclen > 4 and cl_lengths[CL_ORDER[hclen - 1]] == 0:
        hclen -= 1

    bits = HLIT_BITS + HDIST_BITS + HCLEN_BITS
    bits += 3 * hclen
    payload = 0
    for sym, extra, _ in rle:
        payload += cl_lengths[sym] + extra
    bits += payload
    return bits, {"rle_symbols": len(rle), "hclen": hclen,
                  "cl_payload_bits": payload}


def charge_block(tokens: list[Token], context_split: int = 1,
                 token_ctx: list[int] | None = None,
                 final_ctx: int = 0) -> Charge:
    """Charge one block's decoder branches from its real token histograms.

    With ``context_split`` > 1 the block carries one FULL literal/length table
    per context, selected at decode time by a fixed function of the previously
    emitted byte -- which the decoder always knows, for literals and matches
    alike. Splitting only the literal region would leave a context unable to
    express a match, so every context table carries the whole alphabet and
    every one of them is charged.
    """
    ch = Charge()
    ch.block_headers = BLOCK_HEADER_BITS

    if context_split <= 1:
        token_ctx = [0] * len(tokens)
        final_ctx = 0
    assert token_ctx is not None and len(token_ctx) == len(tokens)

    litlen_freqs = [[0] * LITLEN_ALPHABET for _ in range(context_split)]
    dist_freqs = [0] * N_DIST_CODES
    for idx, tok in enumerate(tokens):
        ctx = token_ctx[idx]
        if tok.length == 0:
            litlen_freqs[ctx][tok.literal] += 1
        else:
            lc = length_code(tok.length)
            litlen_freqs[ctx][256 + 1 + lc] += 1
            dc = dist_code(tok.distance)
            dist_freqs[dc] += 1
    litlen_freqs[final_ctx][EOB_SYMBOL] += 1  # branch 7: end-of-block marker

    litlen_lengths = [huffman_lengths(f, MAX_CODE_LEN) for f in litlen_freqs]
    dist_lengths = huffman_lengths(dist_freqs, MAX_CODE_LEN)

    desc_bits, notes = table_descriptor_bits(*litlen_lengths, dist_lengths)
    ch.table_descriptors = desc_bits
    ch.notes.update(notes)

    for idx, tok in enumerate(tokens):
        ctx = token_ctx[idx]
        if tok.length == 0:
            ch.literals += litlen_lengths[ctx][tok.literal]
        else:
            lc = length_code(tok.length)
            ch.lengths += litlen_lengths[ctx][256 + 1 + lc]
            ch.length_extra += LENGTH_EXTRA[lc]
            dc = dist_code(tok.distance)
            ch.distances += dist_lengths[dc]
            ch.distance_extra += DIST_EXTRA[dc]
    ch.eob = litlen_lengths[final_ctx][EOB_SYMBOL]

    if context_split > 1:
        # Context map: 256 previous-byte values -> context id, RLE+Huffman
        # coded with the same machinery. Charged, not assumed free.
        cmap = [context_class(b, context_split) for b in range(256)]
        map_bits, _ = table_descriptor_bits(cmap)
        ch.context_map = map_bits
    return ch


def context_class(byte: int, splits: int) -> int:
    """Fixed, public context function of the previous byte.

    Two-way: whitespace/punctuation vs word bytes -- the split that matters in
    text-like web payloads. Four-way refines the word half into
    digits vs letters.
    """
    is_word = (48 <= byte <= 57) or (65 <= byte <= 90) or (97 <= byte <= 122) \
        or byte == 95
    if splits <= 1:
        return 0
    if splits == 2:
        return 1 if is_word else 0
    is_digit = 48 <= byte <= 57
    if not is_word:
        return 0
    return 2 if is_digit else 1


def store_bytes(orig_len: int) -> int:
    """Store/RAW passthrough: the floor the scheme byte can always select."""
    bits = 8 * FRAME_FIXED_BYTES + varint_bits(orig_len) + varint_bits(1) \
        + BLOCK_HEADER_BITS
    bits = ((bits + 7) // 8) * 8
    return bits // 8 + orig_len + CHECKSUM_BYTES


def parse_blocks(data: bytes, block_size: int | None, max_chain: int,
                 optimal: bool = False,
                 iterations: int = 3) -> list[tuple[bytes, list[Token]]]:
    """Parse a payload into per-block token streams.

    Each block is proven to reconstruct byte-exactly here, so no caller can
    report a size from a stream that does not rebuild its input.
    """
    n = len(data)
    if block_size is None:
        spans = [(0, n)]
        window = max(n, 1)
    else:
        spans = [(s, min(s + block_size, n))
                 for s in range(0, n, block_size)] or [(0, 0)]
        window = block_size
    parsed = []
    for start, end in spans:
        chunk = data[start:end]
        if optimal:
            tokens = lz_parse_optimal(chunk, window=window,
                                      max_chain=max_chain,
                                      iterations=iterations)
        else:
            tokens = lz_parse(chunk, window=window, max_chain=max_chain)
        assert reconstruct(tokens) == chunk, "block does not reconstruct"
        parsed.append((chunk, tokens))
    assert b"".join(c for c, _ in parsed) == data, "file does not reconstruct"
    return parsed


def model_file(data: bytes, block_size: int | None, max_chain: int,
               context_split: int = 1,
               parsed: list[tuple[bytes, list[Token]]] | None = None) -> dict:
    """Model one payload end to end and return its itemised charge."""
    n = len(data)
    if parsed is None:
        parsed = parse_blocks(data, block_size, max_chain)

    total = Charge()
    total.frame_header = (8 * FRAME_FIXED_BYTES + varint_bits(n)
                          + varint_bits(len(parsed)))
    total.checksum = 8 * CHECKSUM_BYTES

    reconstructed = bytearray()
    for chunk, tokens in parsed:
        reconstructed.extend(chunk)
        token_ctx = None
        final_ctx = 0
        if context_split > 1:
            token_ctx = []
            pos = 0
            for tok in tokens:
                prev = chunk[pos - 1] if pos > 0 else 32
                token_ctx.append(context_class(prev, context_split))
                pos += 1 if tok.length == 0 else tok.length
            final_ctx = context_class(chunk[-1] if chunk else 32,
                                      context_split)
        total.add(charge_block(tokens, context_split, token_ctx, final_ctx))

    assert bytes(reconstructed) == data, "file does not reconstruct"

    modelled = total.total_bytes()
    store = store_bytes(n)
    chosen = min(modelled, store)
    return {
        "modelled_bytes": modelled,
        "store_bytes": store,
        "chosen_bytes": chosen,
        "selected": "store" if store <= modelled else "web-scheme",
        "charge_bits": total.items(),
        "total_bits": total.total_bits(),
        "blocks": len(parsed),
    }
