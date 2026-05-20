# Postgres to Snowflake Example

This example shows an authored Recon project for validating a canonical
Postgres source output against a Snowflake target output.

The contract compares customer revenue by `customer_id` and `month`, runs
basic equivalence checks, and declares an aggregate revenue metric.

## Files

```text
recon_project.yml
contracts/customer_revenue.yml
sample_policies/
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
