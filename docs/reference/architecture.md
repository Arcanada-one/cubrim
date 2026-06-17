# Reference: Architecture / System Map

> Stub (Diátaxis: reference). The canonical algorithm spec is born in `consilium/rulebook.md`; this file maps the implementation once code exists.

## Pipeline (proposed, pending consilium)

```
input stream
  → build N-dim cube (edge bound ≤ K, K=256 candidate)
  → shift values to cube corner
  → per-axis distance-map (gap-to-next encoding)
  → compress distance-map (compact run encoding)
  → emit: [distance-map] + [per-value short bit-sequences, width known ahead]
  = compressed file
```

- [TODO: finalize after Phase 0 consilium rulebook]
