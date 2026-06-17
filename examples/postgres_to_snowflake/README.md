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

This is a project and contract fixture for the framework design. `recon parse`
and `recon compile` are implemented for the current parser and compiler scope.
`recon run` is implemented for already compiled, relation-backed same-context
DuckDB row-count and bounded local/dev grain-key safety checks. This fixture
remains a design example rather than an end-to-end executable cross-adapter run.

Generated artifacts are written under `target/`. Future evidence and state
outputs belong under `reports/` and `state/`. Those directories should not be
committed.
