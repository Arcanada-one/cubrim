# LEGAL-0001 License Recommendation

Date: 2026-07-09
Project: Cubrim
Temporary canonical publication target: `cubrim.com`
Future canonical publication target: `legal.arcanada.ai`

This is an engineering/legal-policy recommendation, not legal advice. Arcanada
should obtain professional legal review before relying on the commercial EULA
or any enforcement position.

## Business Goal

Cubrim should be free for non-commercial use and paid for commercial use. The
commercial target from the operator brief is USD 50 per year per named user
seat or per computer/device on which Cubrim is installed.

The current MIT metadata is unsuitable because MIT grants broad permission,
including commercial use, without payment. Also, prior copies actually received
under MIT may retain the MIT rights granted for those copies; this task changes
the licensing package for this release and later releases that reference it.

## Sources Reviewed

- PolyForm Noncommercial License 1.0.0, official text:
  <https://polyformproject.org/licenses/noncommercial/1.0.0>
- Business Source License 1.1, MariaDB official text:
  <https://mariadb.com/bsl11/>
- Cargo manifest license and license-file fields:
  <https://doc.rust-lang.org/cargo/reference/manifest.html#the-license-and-license-file-fields>

## Candidate Comparison

| Candidate | Fit | Strengths | Risks / Tradeoffs |
| --- | --- | --- | --- |
| PolyForm Noncommercial 1.0.0 plus commercial EULA | Best fit | Directly maps free use to non-commercial purposes and routes commercial use to a separate paid grant. Recognized source-available family. Easy to version as Legal Arcana policy. | Not OSI open source. Commercial boundary still needs attorney review for target jurisdictions and edge cases. |
| BSL 1.1 plus commercial EULA | Partial fit | Recognized business-source model. Explicitly directs non-compliant users to buy a commercial license. Can define extra permitted uses. | Its default structure is non-production use plus a future change license. That is less direct than free non-commercial use and may make commercial use free after the change date if configured that way. |
| Custom non-commercial license plus commercial EULA | Possible but not recommended first | Maximum control over commercial definition, metrics, and ecosystem-specific details. | Lower recognizability, higher drafting risk, and more attorney work. Users and tooling may treat it as opaque. |

## Recommendation

Use PolyForm Noncommercial License 1.0.0 for the free non-commercial path, plus
a separate Cubrim Commercial License/EULA for paid commercial use.

Cargo metadata should use:

```toml
license-file = "LICENSE"
```

The Cargo Book states that `license-file` is appropriate when a package uses a
nonstandard license, and crates.io requires either `license` or `license-file`.
This avoids pretending that the dual commercial/non-commercial package is a
standard SPDX open-source expression.

## Commercial Metric

Use this operative metric in the EULA:

> USD 50 per year for each licensed unit. A licensed unit is either one named
> user seat or one computer, server, virtual machine, container host, build
> worker, or other device on which Cubrim is installed or made available for
> execution.

Default to the device metric when a purchase confirmation does not state a
metric. This avoids ambiguity for automated build systems, shared servers, and
service accounts.

## Dependency License Finding

`cargo metadata` and `cargo tree` show no Rust dependencies for the current
`cubrim` package. No third-party dependency copyleft conflict was found in the
audited graph. See `documentation/legal/license-audit.md`.

## Legal Review Items

Before production use, counsel should choose or complete:

- formal licensor entity name;
- governing law and venue;
- tax and payment terms;
- export-control language;
- support commitments, if any;
- data/privacy terms, if the sales process collects customer data;
- treatment of past MIT-tagged releases and public communications around the
  licensing change.
