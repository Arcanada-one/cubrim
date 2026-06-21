# Vendored Dependencies

Scripts in this directory are VENDORED copies from the Datarim framework.
Do NOT edit them directly — update from source and re-vendor.

## Vendored files

| File | Source (absolute path) | Vendored at |
|------|------------------------|-------------|
| `jsonl-write.sh` | `Projects/Datarim/code/datarim/plugins/dr-fleet-evolution/lib/jsonl.sh` | 2026-06-21 |

## Why vendor instead of symlink?

The Cubrim cluster runs on a dedicated host (AX41 HEL1) that has the Cubrim
repo cloned but does NOT have the full Arcanada workspace or Datarim framework
installed. Vendoring ensures the cluster is self-contained and reproducible.

## Re-vendoring

```bash
# From the Cubrim repo root, re-vendor from Datarim source:
cp /path/to/Datarim/code/datarim/plugins/dr-fleet-evolution/lib/jsonl.sh \
   code/cluster/vendor/jsonl-write.sh
# Review and apply any Cubrim-specific extensions from the existing file.
```
