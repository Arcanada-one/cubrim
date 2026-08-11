# Self-update trust model: what the hash check does and does not prove

`cubrim update` replaces the running binary. This note states exactly what
authenticates that replacement today, what does not, and what would.

Read against `code/cubrim-rs/src/self_update.rs` at main `473fafe`.

## The flow

```text
POST https://api.cubrim.com/api/release-check   ->  { version, changelog,
                                                     platforms: [ { os, arch,
                                                                    url,
                                                                    sha256 } ] }
GET  platform.url                               ->  candidate binary
verify_sha256(candidate, platform.sha256)       ->  fs::rename over current_exe (0755)
```

## The defect: the hash and the artefact share a trust root

`platform.sha256` is supplied by **the same response** that supplies
`platform.url`. The check therefore proves that the bytes fetched are the bytes
the manifest *intended* — not that the manifest is honest.

Whoever can write the release-check response can name any URL and the matching
hash. The verification passes, and `replace_current_binary` renames the result
over the running executable with mode `0755`. That is remote code execution on
every installation that updates, and the hash check cannot detect it, because
the attacker computed the hash.

**What the hash check does prove**, and these are real:

- the download was not corrupted in transit or at rest;
- a network attacker who cannot also forge the API response cannot swap the
  binary (the two would disagree);
- it fails closed and removes the temporary file (`self_update.rs`, test
  `sha256_mismatch_fails_closed_and_removes_temp_file`).

**What it does not prove**: that the release is one this project produced.
There is no signature and no trust anchor in the binary. The updater trusts
whatever `CUBRIM_API_BASE_URL` resolves to — and that base is itself an
environment-variable override (`license.rs`), so a caller who controls the
environment redirects the entire update channel.

The release pipeline does not close this either. `.github/workflows/release.yml`
publishes `checksums.txt` alongside the assets — the same channel again, so it
authenticates transfer, not origin. There is no `cosign`, no Sigstore, and no
GitHub artifact attestation anywhere in the workflow.

## What this change does

Two vectors are removed that need no knowledge of the release host, so they can
be closed today without guessing:

- **a plaintext download** — a manifest naming `http://…` is now refused before
  any request is made;
- **credentials in the authority** — `https://user:pass@host/…` is refused.

Validation runs before the temp directory is created, so a rejected URL has no
filesystem side effect at all.

This is defence in depth. **It does not fix the defect above**, and it must not
be reported as having done so: a forged manifest naming
`https://attacker.example/binary` with a matching hash still passes.

Deliberately **not** done: a host allowlist — and on reflection it should not be
added later either. This corrects an earlier reading of this note.

The first reason was practical: the release host is not establishable from this
repository. The manifest is served by the API, `arcanada_cubrim` has no
`release` table, and neither `cubrim-site` nor the database host carries the
handler. Release *assets* do live on GitHub
(`https://github.com/Arcanada-one/cubrim/releases/download/…`), but what the API
actually places in `platform.url` is unverified, and the endpoint cannot be
probed to find out because `usage_payload` would write a `usage_events` row.

The second reason is stronger and does not go away once the host is known: **a
host allowlist compiled into a self-updater is a pin on a mutable identity, in
the one artefact that cannot be re-pinned.** If releases later move to a CDN or
a new domain, every already-installed binary refuses every update — permanently,
because the update path is also the repair path. The failure is silent, delayed,
and unfixable by shipping a new release, since the stranded binaries are exactly
the ones that cannot fetch it.

That is gotcha 12 in `CLAUDE.md` wearing different clothes: freezing an identity
that the world is free to move. Buying a partial mitigation at the price of a
latent mass-stranding is a bad trade for a control that a signature supersedes
anyway.

If a host constraint is ever wanted, it belongs **server-side** — where the
manifest is generated and can be corrected — not compiled into clients that
cannot be reached afterwards.

## What would actually fix it

A trust anchor the binary already holds, checked against a signature over the
release. Concretely, in increasing order of infrastructure:

1. **GitHub artifact attestations** — add `attestations: write` and
   `actions/attest-build-provenance` to `release.yml`, then verify in the
   updater. The ecosystem already has a consumer-side recipe for exactly this
   (`release-verify`: sha256 → `cosign verify-blob` → `gh attestation verify`),
   so the pattern is established rather than novel.
2. **Sigstore keyless signing** (`cosign sign-blob` with OIDC), verified against
   the workflow identity. No long-lived key to store or rotate.
3. **A pinned public key** compiled into the binary, with a documented rotation
   path. Simplest to verify, hardest to rotate — a key compromise requires
   shipping a new binary through the channel being compromised.

Whichever is chosen, the verification must fail closed, and the trust anchor
must **not** be fetched over the same channel as the artefact — that is the
defect being repaired, and re-introducing it would make the signature
decorative.

### Rollout, and why it must be staged

Option 1 is now started: `release.yml` runs
`actions/attest-build-provenance` over the release tarballs and zips, with
`id-token: write` / `attestations: write` on the publish job. The action is
SHA-pinned to the same revision the sibling `datarim` repository already runs in
production, so this is a replicated configuration rather than a new one.

**Producer side only.** The updater still does not require an attestation, and
must not until at least one attested release exists and has been verified with
`gh attestation verify`. Enforcing verification first would reject every release
published before attestation began — which is every release that currently
exists — and strand every installed binary, because the update path is also the
repair path. That is the same stranding failure the host-allowlist section
rejects, arriving from the other direction.

The order is therefore: attest (done here) → cut a release → verify its
attestation out of band → only then teach the updater to require one, failing
closed.

## Status

- Severity is high, exploitability is gated on compromising the API or its
  response path; it is not remotely exploitable by an unprivileged network
  observer, because TLS plus the hash defeats that case.
- Two interactive confirmations stand between a forged manifest and
  replacement, so this is not silent — but a user who has typed `cubrim update`
  will answer both.
- This note records the model. The signature work is a separate task with a
  release-pipeline change and cannot be validated without cutting a release,
  which is why it is not bundled here.
