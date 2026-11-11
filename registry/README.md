# Rights Registry

Each `R-*.yaml` file is a machine-readable research entry. Registry values are research-owned: engineers should not silently change legal values in code. Every entry is still `Seeded` or `Parked` until primary sources, worked examples and peer checks are complete.

Run `python -m engine.registry check` to see status, confidence and unresolved fields.

## Status gates

- **Live mode:** only `Verified` entries may compute.
- **Demo mode:** `Verified` and `Seeded` entries may compute; Seeded outputs must carry `UNVERIFIED RULE`.
- **Parked/Rejected:** never compute.
