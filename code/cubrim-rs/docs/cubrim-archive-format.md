# Cubrim `.cbr` Archive Format

All integers are little-endian unless stated otherwise.

## File Header

```text
magic      4 bytes   ASCII "CUBR"
version    1 byte    0x01 plaintext, 0x02 encrypted
```

Version `0x01` is followed directly by the plaintext payload.

Version `0x02` is followed by:

```text
salt       16 bytes  Argon2id salt
nonce      12 bytes  AES-256-GCM nonce
ciphertext N bytes   encrypted payload plus GCM tag
```

Unknown versions are rejected.

## Payload

```text
entry_count u32
entries     repeated entry_count times
```

Each entry:

```text
path_len        u16
path            path_len UTF-8 bytes, relative path only
kind            u8      0 directory, 1 file
original_size   u64
compressed_size u64
mode            u32     Unix mode when --preserve was used, else 0
mtime           i64     Unix mtime when --preserve was used, else 0
checksum        32 bytes Blake3 hash of original file bytes
data            compressed_size bytes for file entries; absent for directories
```

File data is a legacy Cubrim compressed blob produced by `cubrim::encode`.
Directory entries have zero sizes and no data.

## Path Safety

Archive paths must be UTF-8 relative paths made only of normal path components.
Absolute paths, parent components (`..`), prefixes, root directories, empty paths,
and NUL bytes are rejected while reading and writing archives.
