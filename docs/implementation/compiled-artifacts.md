# Compiled Artifacts

## Purpose

Compiled artifacts make resolved Recon behavior visible before execution.

They are generated outputs under `target/` and should not be committed.

## Artifact paths

Recommended paths:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
```

## Compiled contract

A compiled contract is the resolved version of an authored contract.

It should include:

- contract name,
- source file path,
- source endpoint,
- target endpoint,
- grain,
- columns,
- metrics,
- resolved defaults,
- tolerance policy,
- schema policy,
- CDC policy,
- evidence policy,
- diagnostics.

Example:

```yaml
artifact_type: compiled_contract
artifact_version: 1
contract_name: customer_revenue
source:
  connection: legacy
  relation: qa.v_customer_revenue_compare
target:
  connection: warehouse
  relation: qa.v_customer_revenue_compare
grain:
  keys:
    - customer_id
    - month
```

## Compiled checks

A compiled checks artifact shows exactly what will run.

Example:

```yaml
artifact_type: compiled_checks
artifact_version: 1
contract_name: customer_revenue

checks:
  - name: row_count_diff
    type: row_count_diff
    origin:
      kind: check_pack
      name: recon_core.basic_equivalence
    sampling:
      mode: full
    severity: error

  - name: revenue_by_month
    type: grouped_aggregate_diff
    origin:
      kind: metric
      name: revenue_by_month
    column: revenue
    metric: sum
    group_by:
      - month
    tolerance:
      type: absolute
      value: 0.01
    sampling:
      mode: full
    severity: error
```

## Check origin

Every compiled check should record why it exists.

Possible origins:

```text
explicit_check
metric
check_pack
framework_required_safety_check
```

This helps users understand generated behavior.

## Compiled SQL

Compiled SQL files should be grouped by contract and check.

Example:

```text
target/compiled_sql/customer_revenue/row_count_diff/source.sql
target/compiled_sql/customer_revenue/row_count_diff/target.sql
target/compiled_sql/customer_revenue/revenue_by_month/comparison.sql
```

SQL should be formatted clearly enough for debugging.

## Artifact versioning

Every artifact should include:

```text
artifact_type
artifact_version
generated_at
recon_version
```

`generated_at` may be omitted in golden tests to keep output stable.

## Diagnostics in artifacts

Compiled artifacts should include warnings and validation notes.

Errors should prevent execution unless explicitly allowed.

## Stability

Artifact formats can evolve before 1.0, but changes should be documented.

After artifact formats are used by CI or integrations, changes should be versioned carefully.

## Design principle

Compiled artifacts are the bridge between readable contracts and trustworthy execution.
