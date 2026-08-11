# NEW-24 full-binary G5 admission: terminal VOID before sampling

**State:** immutable terminal evidence. This record does not authorize a G5 retry, a G6 build, or any campaign launch.

## Terminal service identity

- Unit: `cubr-new24-full-binary-g5-admission-20260810.service`
- Invocation ID: `9bb2c1d32c714cf28575e61fcbb601bc`
- Type: `exec`
- Result: `exit-code`
- ExecMainStatus: `1`
- NRestarts: `0`
- ActiveState/SubState: `failed/failed`
- Failure reason: `prebuilt release binary missing or unsafe`
- Terminal main PID: `0`

The service was launched once. It was not restarted, resumed, reset, or launched a second time.

## Immutable failure tree

The only retained output is:

`/root/cubr-new24-full-binary-g5-map-dryrun-20260810.partial`

Its canonical manifest stream has SHA-256 `2d8cbdf7876644a69e176e9578c2b663a12ebe1872ecb1a1048b72c77eb99b15` and 261 bytes. The first path-sorted block is emitted with GNU `find -xdev -printf '%P\t%y\t%m\t%s\n'`. The second path-sorted block contains `sha256`, byte count, and root-relative path for each regular file, tab-separated with one trailing newline per row. The exact 261 bytes are retained at
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/remote-tree-manifest.tsv`,
Git blob `49fb705f5230a35e43726d4f6a333e47c5cb1b29`. The tree contains only:

- `FAILED.STAMP`, mode `0444`, 115 bytes, SHA-256 `cd43d8eb4c9c6ff76659f1ffe33f4d80a35678083b646cf9dc94bcca1e45e4e8`;
- `preflight/journal.tsv`, mode `0444`, 193 bytes, SHA-256 `0203131c33cf51508ef12d47b27be41e956db5e847a7b02c4e620d4cfe8bb4bc`.

The root and `preflight/` directory are mode `0500`. The raw JSON unit-journal
rendering captured at the incident has SHA-256
`b11d33ecde790f61e679494d9e48419688a1aef0e3a979de2eb5b65556597c25`
and 6428 bytes. `journalctl --output=json` does not preserve JSON object-key
order across later renders, so that raw-render hash is historical capture
provenance, not a live re-render predicate. Sorting events by `__CURSOR`, then
sorting every event's JSON keys and serializing with compact separators plus
one trailing newline per event yields the reproducible 6428-byte canonical
stream with SHA-256
`926fdebe5690ce450ce6970c3260c54ce37bd095241f760d2acd9931b0586e4c`.
Those exact bytes are retained at
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-ADMISSION-VOID-20260811/systemd-journal.canonical.jsonl`,
Git blob `5ea61262dacd442fdf1676a7a7613c8e5534b6a3`.

## Exhaustive zero-sample proof

The retained tree contains:

- `perf.data`: 0
- address-smoke raw artifacts: 0
- campaign cell directories: 0
- attribution summaries: 0
- `pstat*.perf-stat.csv`: 0
- `prec*` raw/derived artifacts: 0
- journal rows naming a campaign cell: 0

The final admission output, `.publishing`, and `.late` variants are absent. The G5 campaign unit and all four G5 campaign output variants are absent. The G5 build target is absent. The detached source tree remains clean at `830a9a31deb00926a97f3fa5bd74f58003573fc0`; the detached instrument tree remains clean at resulting main `fdf2717078dcfe0ef6281802baef63ec39dd1cf5`.

## Disposition

G5 is `VOID / NO-SELECT` with `performance_sample=NO`. Its preregistration states that a pre-sampling VOID is preserved and never retried, and that continuation requires a new prospective protocol. No G5 path, unit, process identity, receipt, or partial artifact may satisfy a G6 predicate. Only the immutable incident hashes and byte counts above may be cited as G6 provenance.

The controlling clause is
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md`
lines 507–513, Git blob `5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f`,
reviewed head `e4f7efe84d6478d5f0c7286873910972f87b4d68`, and
resulting main `c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4`. The same
blob remains present on the G5 instrument resulting main
`fdf2717078dcfe0ef6281802baef63ec39dd1cf5`.
