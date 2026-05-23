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

This is a project and contract fixture for the framework design. `recon parse`
and `recon compile` are implemented for the current parser and compiler scope.
`recon run` is registered in the CLI but is not implemented yet.

This example references `recon_core.cdc_equivalence`, which remains future
compiler scope. Current `recon compile` should report that pack as unsupported
rather than silently ignoring it.

Generated artifacts are written under `target/`. Future evidence and state
outputs belong under `reports/` and `state/`. Those directories should not be
committed.
