# Web Profile disclosure policy

**Status: decided, 2026-07-29. Read this before fixing the Web Profile wire
format (CUBR-0076).**

## The conflict this resolves

Two tracks pulled in opposite directions, and the choice becomes irreversible
the moment the wire format is fixed:

- LEGAL-0061 recommended freezing technical disclosure to preserve a patent
  option.
- CUBR-0069 needs a publicly reproducible method, and CUBR-0072/0080 need a
  public specification and reference decoder for IETF and IANA.

Both cannot be maximised. LEGAL-0062 surfaced the conflict; the decision below
resolves it.

## Decision: split public decoder and format from private encoder techniques

**Public: the wire format and the decoder. Private: encoder-side techniques
invented for the web profile.**

The reasoning, recorded so it can be re-examined rather than re-litigated:

- There is no legal entity until September 2026, so no patent could be filed in
  an entity name before then regardless. Freezing disclosure would idle the
  epic for two months.
- Even then it would only buy US and JP. EPC Art. 54/55 and CN Art. 24 make
  already-disclosed matter effectively unpatentable, and LEGAL-0061 found no
  evidenced private core in the existing algorithm.
- A web content-coding whose decoder and format are closed is worthless: the
  entire value is browsers implementing it.
- The genuinely new material — encoder-side technique in the web profile — is
  where any remaining patent option actually lives, and the split keeps exactly
  that private.

## What is public

Proceed normally, no clearance needed:

- the wire format itself: magic, version, flags, window size, block type,
  checksum;
- framing and streaming semantics;
- resource limits;
- the reference **decoder**;
- conformance vectors;
- benchmark methodology and benchmark results.

## What stays private

Do not publish, and keep out of the specification, the reference decoder, and
the benchmark methodology text:

- block-selection heuristics;
- parameter search;
- modelling or dictionary-**construction** methods invented for the web profile.

## The test

**Is it already in the public cubrim source?**

- Yes → it is public, and you may document it.
- No, and it is encoder-side → it stays private.

A worked example: that the web profile uses a shared dictionary, and the
measured effect of doing so, are public. How that dictionary is *constructed*,
if the method is new to the web profile, is private.

## Escalate rather than decide silently

If the format cannot be made implementable without disclosing a **new**
encoder-side internal, that is an operator decision, not an engineering one.
Stop and flag it, naming the specific technique. Do not quietly publish it, and
do not quietly cripple the format to avoid publishing it.

## Unchanged hard gates

IANA/IETF submission, browser-vendor outreach, upstream Chromium pull requests,
and public package release all still require operator sign-off. Prepare them
fully, then stop.
