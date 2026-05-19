# CDC Validation Example

This example shows an authored Recon project for validating an upsert-style CDC
pipeline with explicit soft-delete behavior.

The contract compares orders by `order_id`, declares value columns, configures
CDC mode and delete behavior, ignores expected target-side CDC metadata columns
for schema checks, and references an incremental-window sampling policy.

## Files

```text
recon_project.yml
contracts/orders_cdc.yml
sample_policies/latest_changed_records.yml
tolerances/
schema_policies/
```

## Current Status

This is a project and contract fixture for the framework design. `recon parse`,
`recon compile`, and `recon run` are registered in the CLI but are not
implemented yet.

Generated artifacts should be written under `target/`, `reports/`, and
`state/` once those commands are implemented. Those directories should not be
committed.
