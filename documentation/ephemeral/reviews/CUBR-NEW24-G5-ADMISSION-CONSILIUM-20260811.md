# Consilium recommendation: G5 admission VOID disposition

## Question

After the one-shot G5 no-performance admission failed because its preregistered materialization procedure omitted the binary build, should the program terminate, retry G5, or continue under a new protocol?

**Blast radius:** business-critical evidence integrity across the NEW-24 performance branch.

**Panel:** Chief Architect, SRE, Senior Developer.

**Controlling authority:**
`documentation/ephemeral/research/CUBR-NEW24-FULL-BINARY-G5-20260810.md`
lines 507–513, blob `5a0eb4c18b2cd407d0135e0ca2130b3b27d84b6f`,
reviewed head `e4f7efe84d6478d5f0c7286873910972f87b4d68`, resulting
main `c498c0560b6c25c1cf0327ec809cefbf4dbe0dd4`.

## Independent positions

### Chief Architect — conditional support for a prospective recovery

The deterministic plan defect occurred before performance sampling, so scientific continuation is defensible. Reusing the G5 unit or output is not. The architect preferred a protected, separately named recovery protocol and identified G6 as the strict-governance fallback.

### SRE — conditional GO for a new protocol generation

The original invocation consumed its exactly-once allowance and must remain immutable. Reliability requires disjoint units and paths, two clean builds of the frozen binary, one new admission, and no third attempt. The failed G5 unit/tree remains incident evidence.

### Senior Developer — oppose any second G5 identity

The landed G5 preregistration explicitly says a pre-sampling VOID routes to a new prospective protocol, not another G5 attempt. The developer therefore required G6, a pre-service two-build gate, mutation-tested identity checks, and unchanged scientific thresholds.

## Conflict and convergence

| Conflict | Resolution |
|---|---|
| Architect/SRE considered a separately named G5 recovery defensible; Developer required G6. | The landed preregistration is explicit: G5 has no second launch and a pre-sampling VOID requires a new prospective protocol. Correctness outranks implementation simplicity. |
| Immediate termination is the strictest literal route; continuation preserves the unchanged scientific question. | Continue only as G6, with no reuse of G5 runtime artifacts and no build before the G6 preregistration lands. |

## Recommendation

Preserve G5 permanently as `VOID / NO-SELECT`. Fork the smallest prospective G6 with unchanged source commit, candidate, cells, ceilings, thresholds, CPU pin, and thread limits. Change only protocol identity, namespaces, deterministic prebuild mechanics, and provenance binding.

Before any G6 service exists, two independent clean source/target pairs must generate byte-identical frozen lockfiles and binaries that also equal the already frozen G5 identities. Any mismatch is `NO-ATTEMPT`; expected identities are never changed to match an observed build. A successful prebuild may authorize one G6 no-performance admission. A failed G6 admission is terminal; there is no G6 admission retry.

## Failure modes

| What can fail | Impact | Detection | Mitigation |
|---|---|---|---|
| G5 evidence is reused or altered | Critical provenance loss | Hash/byte mismatch or G5 path in a G6 seal | Preserve G5; allow incident hashes only |
| Two builds differ or miss frozen identities | G6 cannot start | Lock, binary SHA, build ID, toolchain comparison | `NO-ATTEMPT`; never adjust expectations |
| G6 namespace collides | Ambiguous attempt identity | Pre-service absence gate | No deletion or repair; `NO-ATTEMPT` |
| G6 admission fails | No campaign authority | Terminal unit/tree and zero-sample audit | Preserve VOID; no second G6 admission |
| Campaign is launched before protected identities land | Invalid evidence | Exact-main blob and ancestry gates | `NO-LAUNCH` |

## Conditions

- The G5 incident record and G6 preregistration land before any G6 build.
- G6 uses entirely new source, target, instrument, admission, campaign, and unit namespaces.
- Both independent builds use the frozen source/toolchain/flags and match every frozen identity.
- Prebuild and runner controls are TDD- and mutation-tested.
- Admission is no-performance and one-shot; campaign is separately one-shot.
- Database, site, social, and credential paths remain untouched.
