# FH-BIFF2 — BIFF2 record-group transform

## Evidence

Read-only inventory of Canterbury `kennedy.xls` (SHA256
`9af47239ca29dfe20e633f80bbbb9a4cc9783d0803d7b2b5626f42e4c3790420`):

- 1,029,744 bytes; 79,241 complete `[type:u16 LE][len:u16 LE][payload]` records.
- 13 distinct record types and, on this file, 13 `(type,len)` groups.
- `(0x0005,9)`: 57,200 records, 743,600 wire bytes, 72.2121%.
- `(0x0002,9)`: 21,173 records, 275,249 wire bytes, 26.7298%.
- Three final bytes `05 00 09` form a truncated next header and must be preserved.

The two fixed-width cell groups occupy 98.9420% of the file. This falsifies the
earlier assumption that RK/NUMBER records dominate, but strengthens a simpler
structural hypothesis: repeated four-byte headers and fixed payload positions
can be represented directly without semantic BIFF field parsing.

## Decision

Add a forced-only top-level `MODE_BIFF = 12`. Parse all complete records, group
them by exact `(type,len)`, replace each record header in the sequence with one
`u8` group id, and byte-plane transpose each group's payload matrix. Encode the
group-id sequence and each complete transposed group stream with existing
`encode_base`. Preserve the unmatched tail verbatim.

Alternatives rejected for this spike:

1. Generic stride detection cannot represent interleaved BIFF record types.
2. A semantic BIFF2 parser is premature until the structural gain is measured.
3. Modifying MODE_SOA would mix format-specific framing into a generic mode.

## Wire

All container integers are big-endian; BIFF record type/length values remain
the original little-endian numeric values.

```text
[MAGIC 4B][VERSION 1B][MODE_BIFF 1B]
[orig_len u64][raw_hash64 u64][n_records u32][n_groups u16][tail_len u32]
[key_blob_len u32][key_blob]
n_groups * [record_type u16][payload_len u16][count u32][blob_len u32][blob]
[tail bytes]
```

Group ids are assigned in sorted `(type,len)` order and are indexes into the
serialized group list. The key blob must decode to exactly `n_records` bytes.
Each group blob must decode to exactly `payload_len * count` bytes, arranged as
all byte-0 values, then all byte-1 values, and so on. Reconstruction walks the
key sequence, takes the next row from the selected group, emits the original
four-byte LE record header and payload, then appends the exact tail.

## Safety

- Input must contain at least one complete record and at most 256 groups.
- Parsing stops only at an incomplete header/record; all remaining bytes become
  charged residual tail. No bytes are discarded.
- All products, sums, offsets and allocations use checked arithmetic.
- Decoder rejects unknown group ids, count mismatches, truncated/extra nested
  payload, reconstructed length mismatch and final hash mismatch.
- No default dispatcher call and no DB write before real full-24 evidence.

## Verification and falsification

1. Synthetic mixed-record and truncated-tail RT tests.
2. Malformed group id, length, nested stream and hash tests.
3. Ignored dev-ai spike on the exact `kennedy.xls`: forced MODE_BIFF bytes,
   current competitive rail bytes, RAR leader bytes from the same file,
   RT=OK/cmp=0 and exact ratios.
4. If mode 12 does not beat current Cubrim, stop. If it improves but remains
   above the remeasured RAR leader, use the measured residual by payload column
   to decide whether semantic integer/Boolean coding is justified.
5. Only a leader-beating result proceeds to competitive-min full-24. The mode
   remains unselected elsewhere, so no claim is made before that run.
