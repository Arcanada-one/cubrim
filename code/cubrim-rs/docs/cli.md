# Cubrim CLI

Cubrim supports two formats:

- Legacy single-file Cubrim blobs from `compress` / `decompress`.
- `.cbr` archives for multiple files and directories.

## Single Files

```sh
cubrim compress input.bin input.cub
cubrim c input.bin input.cub
cubrim decompress input.cub restored.bin
cubrim d input.cub restored.bin
cubrim x input.cub restored.bin
```

The single-file commands call the existing codec API and preserve the legacy byte stream.

## Archives

```sh
cubrim a archive.cbr file.txt dir --force
cubrim x archive.cbr -o restored
cubrim l archive.cbr
cubrim t archive.cbr
```

`-q` suppresses progress output. `--force` allows overwriting outputs. Without
`--force`, Cubrim fails rather than replacing an existing archive or extracted file.

## Password Archives

```sh
cubrim a secret.cbr dir --password
cubrim x secret.cbr -o restored --password
```

Passing `--password` with no value prompts without echo. Passing
`--password value` is supported for automation but can expose the password in
shell history or process listings.

## Exit Codes

- `0`: success
- `1`: usage or input error
- `2`: archive integrity, checksum, codec decode, or authentication failure
- `3`: filesystem I/O error
