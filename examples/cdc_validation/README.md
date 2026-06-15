# CDC Validation Example

This example shows an authored Recon project for validating an upsert-style CDC
pipeline with explicit soft-delete behavior.

The contract compares orders by `order_id`, declares value columns, configures
CDC mode, declares CDC identity explicitly with `cdc.keys`, configures delete
behavior, ignores expected target-side CDC metadata columns for schema checks,
and references an incremental-window sampling policy.

## Files

```text
recon_project.yml
contracts/orders_cdc.yml
sample_policies/latest_changed_records.yml
tolerances/
schema_policies/
```

## Current Status

This is a future/negative design fixture for the framework design, not a
currently executable CDC example. `recon parse` is implemented for the current
parser scope, but `recon compile` is expected to reject the unsupported future
surfaces used here. `recon run` is implemented for already compiled,
relation-backed same-context DuckDB row-count and bounded local/dev grain-key
safety checks, but CDC execution remains future scope.

This fixture intentionally includes current compile blockers:

- `recon_core.cdc_equivalence` remains future compiler scope. Current
  `recon compile` should report that pack as unsupported rather than silently
  ignoring it.
- `columns.timestamp[].tolerance: 5 seconds` remains future timestamp tolerance
  scope. Current `recon compile` should reject that unsupported tolerance syntax
  rather than treating timestamp tolerance as executable behavior.

Generated artifacts are written under `target/`. Future evidence and state
outputs belong under `reports/` and `state/`. Those directories should not be
committed.
