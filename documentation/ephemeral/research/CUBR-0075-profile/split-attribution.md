# CUBR-0075 — Model Split Attribution

Status: `COMPLETE`. The feature-gated split run produced 792/792 exact
round-trips: 12 samples, 3 warmups plus 30 measured trials, in one-core and
fixed-core modes. The table covers the 720 measured observations; shares are
of the three applicable split rows.

| Split | Measured cycles | Calls | Cycles/call | Share |
|---|---:|---:|---:|---:|
| `model.counter_state_lookup` | 676,555,572,686 | 452,038,080 | 1,496.68 | 28.3412% |
| `model.dot_products` | 467,134,380,580 | 452,038,080 | 1,033.40 | 19.5684% |
| `model.adaptation` | 1,243,493,652,544 | 452,038,080 | 2,750.86 | 52.0904% |

Boundaries: counter/state lookup covers `predict_bit` provider, state, and
input preparation before the mixer phase; dot products cover mixer-context
setup, five layer-1 `Mixer::mix` calls, layer-2 `Mixer::mix`, and squash;
adaptation covers the entire `update_bit`. The post-mixer APM refinement tail
is outside the first two guards and remains represented by the existing
`entropy.predict_bit` substage.

Provenance: source `d3c345cb8be7baf4abb77a471e402d4bad0893e3`; profile binary
`7b1d1f786885c3f2866d84c7e3895d5d85aff966578be9bbbf08c0fd0fd46d04`; encoder binary
`144684151ba90deb8bcad0c659f78a9dc40941eb7d8cbb4b18534cf931c2ec03`; manifest
`fecc83c1e6559d361d0029024393a3cc98909f0c45dea3a2f0c4f11b75a3a2bf`.

No optimization, decoder/wire-format change, or database write was made.
