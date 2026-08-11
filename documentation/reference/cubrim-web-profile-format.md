# Cubrim Web Profile — wire format specification, version 1

**Status:** normative for `MODE_WEB` version 1 as shipped in `cubrim`
(`code/cubrim-rs/src/web.rs`) and in the reference decoder
(`code/cubrim-web-decoder`). Task CUBR-0076, epic CUBR-0072.
**Audience:** anyone writing a decoder for `application/cubrim`.

**Disclosure:** this document is **public** under the CUBR-0072 / ADR-0003
split — wire format, framing, limits and the reference decoder are public;
encoder-side technique is not. Everything here is what a decoder must know.
Nothing here constrains how an encoder chooses its parse, its block geometry or
its tables; two encoders producing different bytes are both conformant if both
outputs decode to the original input.

RFC 2119 keywords. All multi-byte integers are big-endian. The bitstream is
**MSB-first**: the first bit of a field is the most significant bit of the byte
it starts in.

## 1. Scope and intent

The Web Profile exists to make decode cheap, not to make output small. It
transmits **static entropy tables in the block header and adapts nothing at
decode time**, so a decoder is a flat table lookup per symbol. Measured on the
12-sample web census: 0.9361 the size of gzip -9, 1.1147 the size of brotli -11,
decoded at 443 MB/s natively and 99 MB/s in a browser through WebAssembly.

A conformant decoder MUST reproduce the original bytes exactly or fail. There
is no lossy mode, no partial-output mode, and no "best effort".

## 2. Frame

```
 offset  size  field
      0     4  MAGIC          = CB 52 49 4D   ("\xCBRIM")
      4     1  VERSION        = 1
      5     1  MODE           = 18            (MODE_WEB)
      6     4  ORIG_LEN       uncompressed length in bytes, u32 BE
     10     4  CHECKSUM       first 4 bytes of BLAKE3(original bytes)
     14     …  BITSTREAM      one or more blocks, MSB-first
```

A decoder MUST reject a frame whose MAGIC, VERSION or MODE does not match.
`ORIG_LEN` is untrusted: it MUST be checked against the caller's output budget
**before** allocating, and the decoded length MUST equal it exactly at the end.

The frame carries no length field for the bitstream: the final block's
end-of-block symbol terminates it. Trailing bytes after that symbol (up to the
byte-alignment pad) MUST be ignored.

## 3. Block

Each block begins on a bit boundary, not a byte boundary.

```
  1 bit   BFINAL    1 = last block in the frame
  2 bits  BTYPE     1 = one literal/length table
                    2 = three literal/length tables, context-selected
                    0, 3 = reserved; a decoder MUST reject them
  5 bits  HLIT      number of literal/length codes present, minus 257
  6 bits  HDIST     number of distance codes present, minus 1
  4 bits  HCLEN     number of code-length-code lengths present, minus 4
```

`HLIT + 257` MUST NOT exceed 286. `HDIST + 1` MUST NOT exceed 64. `HCLEN + 4`
MUST NOT exceed 19.

`HDIST` is six bits, unlike DEFLATE's five: the distance alphabet is extended
past 32 KiB (§6) and can exceed 32 codes.

## 4. Table descriptors

Immediately after the block header:

1. `HCLEN + 4` code lengths, **3 bits each**, for the code-length alphabet, in
   this fixed order:

   ```
   16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15
   ```

   Lengths for symbols not present are 0. Maximum code length: **7**.

2. A single RLE-coded sequence of code lengths, Huffman-coded with the
   code-length alphabet, covering — in order:

   - the literal/length table for context 0, `HLIT + 257` entries;
   - for `BTYPE = 2` only: the same for context 1, then context 2;
   - the distance table, `HDIST + 1` entries.

   Code-length alphabet semantics:

   | symbol | meaning | extra bits | run |
   |---|---|---|---|
   | 0–15 | this code length, once | 0 | 1 |
   | 16 | repeat the **previous** length | 2 | 3–6 |
   | 17 | repeat zero | 3 | 3–10 |
   | 18 | repeat zero | 7 | 11–138 |

   Symbol 16 at the very start of the sequence is invalid. A run that would
   overrun the expected total is invalid.

Maximum literal/length and distance code length: **14 bits**. (Fourteen, not
DEFLATE's fifteen, so a decoder can use one flat 2^14-entry lookup table.)

Every constructed code MUST be a complete prefix-free code — the Kraft sum over
present symbols MUST equal exactly 1 — with one exception: an alphabet where
exactly one symbol is present MUST give it length 1. Anything else MUST be
rejected.

Codes are **canonical**: symbols are ordered by `(code length, symbol index)`
ascending, the first code of the shortest length is all-zero bits, and each
subsequent code is the previous plus one, shifted left when the length grows.

## 5. Literal/length alphabet

286 symbols:

| symbol | meaning |
|---|---|
| 0–255 | a literal byte |
| 256 | end of block |
| 257–285 | a match length code (§7) |

Symbols above 285 MUST be rejected.

### Context selection (BTYPE = 2)

The table used to decode the **next** symbol is chosen by the previously
emitted byte — which the decoder always knows, after a literal and after a
match alike. At the start of a block, the previous byte is taken to be `0x20`
(space).

```
context(b) = 0   if b is not a word byte
             2   if b is an ASCII digit
             1   otherwise (ASCII letter or '_')

word byte := ASCII letter, ASCII digit, or '_' (0x5F)
```

Every context carries the **whole** alphabet, including length codes and
end-of-block, so a match can be expressed in any context. There is no
transmitted context map: the function above is frozen in this specification.

For `BTYPE = 1` the context is always 0.

## 6. Distance alphabet

Up to 64 codes. Code *i* covers distances `[BASE[i], BASE[i] + 2^EXTRA[i])`:

```
code   0  1  2  3   4  5   6  7    8   9   10  11  …
base   1  2  3  4   5  7   9  13   17  25  33  49  …
extra  0  0  0  0   1  1   2  2    3   3   4   4   …
```

Formally: codes 0–3 are distances 1–4 with no extra bits; thereafter each pair
of codes adds one extra bit and continues from the previous code's end. This is
DEFLATE's construction, continued past its 30-code limit — that continuation is
what allows a window larger than 32 KiB.

A decoder MUST reject a distance code at or above the number of codes the block
declared, and MUST reject a decoded distance of 0 or one larger than the bytes
already emitted.

## 7. Length alphabet

Length code `c` (symbol `257 + c`) covers lengths `[LBASE[c], LBASE[c] + 2^LEXTRA[c])`:

```
LBASE  = 3 4 5 6 7 8 9 10 11 13 15 17 19 23 27 31 35 43 51 59 67 83 99 115 131 163 195 227 258
LEXTRA = 0 0 0 0 0 0 0  0  1  1  1  1  2  2  2  2  3  3  3  3  4  4  4   4   5   5   5   5   0
```

Minimum match length 3, maximum 258. Code 285 encodes exactly 258 with no extra
bits. A decoded length outside 3–258 MUST be rejected.

## 8. Symbol sequence

Within a block, repeatedly:

1. Decode one symbol from the literal/length table for the current context.
2. If it is 256, the block ends.
3. If it is below 256, emit it as a literal byte.
4. Otherwise it is a length code: read its extra bits to get the match length,
   then decode one symbol from the **distance** table and read its extra bits to
   get the distance, then copy `length` bytes from `distance` bytes back in the
   already-emitted output.

**The copy is byte-at-a-time semantics.** When `distance < length` the run
overlaps and later bytes read what earlier bytes of the same copy just wrote —
this is how run-length repeats are expressed. An implementation MAY use a block
copy only when `distance >= length`.

A match MUST NOT make the output exceed `ORIG_LEN`, and a literal MUST NOT be
emitted once the output has reached it.

## 9. Termination and verification

After the block with `BFINAL = 1`:

- the decoded length MUST equal `ORIG_LEN`;
- `BLAKE3(output)[0..4]` MUST equal `CHECKSUM`.

If either check fails the decoder MUST report failure and MUST NOT return the
output. The checksum is an integrity check against corruption, **not** an
authentication mechanism: it is four bytes and unkeyed, and MUST NOT be relied
on to detect deliberate tampering.

## 10. Limits a decoder must enforce

Untrusted input reaches every field. A conformant decoder:

- MUST enforce a caller-supplied maximum output size against `ORIG_LEN` before
  allocating, and MUST NOT exceed it while decoding;
- MUST reject every malformed field named above rather than clamping it;
- MUST NOT panic, abort, hang or read out of bounds on any input, valid or not;
- MUST NOT return partial output on failure.

The reference decoder's default output ceiling is 64 MiB.

## 11. Conformance

A decoder is conformant if, for every frame this specification calls valid, it
reproduces the original bytes, and for every frame it calls invalid, it reports
failure.

Two independent implementations ship in this repository and are held to that by
a differential test (`code/cubrim-web-decoder/tests/differential.rs`) that runs
both against the census corpus, synthetic shapes, and thousands of single-bit
mutants, failing on any disagreement about output **or about validity**. New
implementations are encouraged to reuse it.

## 12. What this version does not have

Stated so that a reader does not have to infer it:

- **No dictionary.** Nothing is shared across frames.
- **No streaming API in the reference decoder**, though `BFINAL` exists and the
  format permits multiple blocks; the shipped encoder emits a single block per
  frame, so the multi-block path is defined here but not yet exercised.
- **No encryption or authentication.**
- **No compressed-size field**, so a frame cannot be skipped without decoding.
- **No self-describing window size**: the window is bounded by `ORIG_LEN`,
  because a match can only reference bytes already emitted.

## 13. Version policy

`VERSION` is the frame's, and this document specifies `VERSION = 1` with
`MODE = 18`. Any change to the meaning of existing bits requires a new
`VERSION`; a decoder MUST reject versions it does not implement rather than
guessing. Reserved `BTYPE` values 0 and 3 are the intended extension point for
adding block types without a version bump — a decoder that rejects them today
stays correct when one is defined, because it will refuse rather than
misinterpret.
