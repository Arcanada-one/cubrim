# Packed Ctr zero-representation local gates

**Implementation base:** `1e8d40d064d21149ed40040a61f24b916fae9a25`

This is pre-measurement implementation evidence. It contains no RSS or speed
result and does not make the candidate eligible to ship.

## Clean baseline

From the exact implementation base, before editing `cm2.rs`:

```text
cargo test --release
library: 320 passed; 0 failed; 11 ignored
integration: main 7; cli_archiver 5; cubr0027 2; cubr0028 1;
cubr0031 1; differential 10; hostile_inputs 6; scheme_roundtrip 7
```

All integration suites passed. The baseline emitted the same three existing
library warnings later seen on the candidate. The two benchmark integration
tests rewrote their tracked JSON result files; because the tree was clean before
the command, those exact test-generated changes were surgically restored.

## Test-first RED

The two focused tests were added before production code.

1. `ctr_zero_representation_starts_zero_and_predicts_midpoint`
   failed on the current packed implementation at the unconditional assertion:

   ```text
   assertion failed: ctr.v.iter().all(|&word| word == 0)
   ```

2. `ctr_zero_representation_update_preserves_logical_fields`
   failed on the current packed write representation:

   ```text
   assertion `left == right` failed
     left: 3072
    right: 1024
   ```

Both were assertion failures caused by the missing representation, not compile
errors or fixture errors.

## Minimal implementation

The implementation adds one private midpoint-bias constant, initializes the
packed vector with physical zero words, XOR-decodes the probability on both read
paths, and XOR-encodes it on write. It does not change the logical update
formula, count/state bytes, table indexing, wire format, or decoder.

After implementation, both exact focused tests passed independently.

## Mutation-sensitive RED/GREEN

Each mutation was applied surgically, run once, then surgically restored before
the GREEN control:

| Mutation | Decisive RED assertion | Restored control |
| --- | --- | --- |
| Restore the old non-zero initializer | physical-zero assertion failed | initialization test passed |
| Remove the `predict` read XOR | stationary probability left `0`, right `2048` | both focused tests passed |
| Remove the updated-probability write XOR | logical probability left `1024`, right `3072` | both focused tests passed |

Final focused control:

```text
cargo test --release --lib ctr_zero_representation
2 passed; 0 failed; 331 filtered out
```

## Post-change local gates

```text
cargo fmt --check
PASS

cargo test --release
library: 322 passed; 0 failed; 11 ignored
integration: main 7; cli_archiver 5; cubr0027 2; cubr0028 1;
cubr0031 1; differential 10; hostile_inputs 6; scheme_roundtrip 7

cargo test --release --test scheme_roundtrip
7 passed; 0 failed

python3 isolated-venv -m pytest --strict-markers reproducibility/test_verify.py
12 passed
```

The first reproduction attempt used the plan's CI spelling `python -m pytest`
and exited 127 before test collection because this host has neither a `python`
shim nor a preinstalled `pytest` module. The CI workflow explicitly installs
pytest. An isolated temporary Python 3.12.3 venv reproduced that dependency
step and the unchanged 12-test verifier passed. No repository or system Python
state was modified.

The post-change benchmark tests again rewrote the same two tracked JSON files;
only those proven test-generated changes were restored. They are not part of
the candidate diff.
