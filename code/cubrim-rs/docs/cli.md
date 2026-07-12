# Cubrim CLI

Cubrim's public command-line interface is archive-first and `.cbr`-only.

## Public Commands

```sh
cubrim
cubrim a archive.cbr file.txt dir --force
cubrim x archive.cbr -o restored
cubrim e archive.cbr -o flat
cubrim l archive.cbr
cubrim t archive.cbr
cubrim d archive.cbr '*.tmp'
```

Public surface:
- `a` / `add` — create an archive or add paths
- `x` / `extract` — extract with stored paths
- `e` / `extract-flat` — extract flat by terminal filename
- `l` / `list` — list members
- `t` / `test` — verify archive integrity without extraction
- `d` / `delete` — remove members from an archive

Bare `cubrim` prints version + help and exits `0`.

## License Gate

On first use, Cubrim shows a short license summary and asks for explicit
acceptance before running archive commands. Acceptance is stored in the user
configuration directory as `cubrim/state.json` with a random install UUID,
accepted license version, and timestamp. Later runs skip the prompt.

```sh
cubrim --license
cubrim --accept-license
CUBRIM_ACCEPT_LICENSE=1 cubrim t archive.cbr
```

Prompt contract:
- `[Y/n]`
- pressing Enter accepts
- `y`, `yes`, and empty input accept
- `n` or `no` reject

License and release requests send only `install_id`, `os`, `arch`,
`cli_version`, and `event_type`. Cubrim never sends hostnames, usernames,
paths, file contents, or project data. If the license endpoint is unavailable,
the binary displays its embedded offline license summary.

## Archive Semantics

With `--preserve`, Cubrim archives and restores:
- regular files
- directories, including empty directories
- symlinks as symlinks
- hardlink identity
- Unix `mode`
- `mtime`
- xattrs
- Unicode filenames
- non-UTF-8 path bytes on Unix

Extraction is fail-closed against:
- path traversal in member paths
- absolute symlink targets
- symlink targets that escape the extraction root
- checksum mismatch
- wrong archive password

## Password-Protected Archives

```sh
cubrim a secret.cbr dir --password
cubrim x secret.cbr -o restored --password
```

Passing `--password` with no value prompts without echo. Passing
`--password value` is supported for automation but can expose the password in
shell history or process listings.

## Self Update

```sh
cubrim --update
```

`--update` checks the latest stable release, downloads the matching platform
binary, verifies SHA256, shows changelog text, and asks before replacing the
current executable. A checksum mismatch leaves the current binary untouched.

## Internal Benchmark Surface

The world-benchmark blob engine still exists for research and measurement, but
it is not part of the public CLI contract and does not appear in `--help`.
Internal harnesses may still call the hidden `compress` / `decompress` verbs to
measure the raw codec path without `.cbr` container overhead.

## Exit Codes

- `0`: success
- `1`: usage or input error
- `2`: archive integrity, checksum, codec decode, or authentication failure
- `3`: filesystem I/O error
