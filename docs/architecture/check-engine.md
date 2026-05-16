# Check Engine Architecture

## Purpose

The check engine executes compiled checks and returns structured results.

The engine should be independent from the CLI and should interact with databases only through adapters.

## Inputs

The check engine receives:

```text
CompiledCheck
ExecutionContext
AdapterRegistry
StateBackend
EvidenceWriter
```

## Outputs

The check engine returns:

```text
CheckResult
FailureDetail references
EvidenceArtifact references
Diagnostics
```

## Check lifecycle

Recommended lifecycle:

```text
validate check requirements
prepare execution
generate SQL or adapter request
execute
collect result values
collect failure details when configured
return CheckResult
```

## Check registry

Checks should be registered by type.

Example:

```text
row_count_diff
missing_keys
extra_keys
duplicate_source_keys
duplicate_target_keys
sum_diff
grouped_aggregate_diff
exact_value_match
numeric_tolerance_match
schema_equivalence
freshness_lag
```

The registry should allow built-in checks and later package-provided checks.

## Check interface

A check implementation should declare:

- check type,
- required config,
- required contract context,
- required adapter capabilities,
- whether keys are required,
- whether unique keys are required,
- whether columns are required,
- supported sampling modes,
- result schema.

## Row-level checks

Row-level checks require `grain.keys`.

Value-level row checks require unique keys in source and target.

Duplicate-key checks should run before row-level value checks.

If duplicates are found, row-level value checks should be blocked.

## Aggregate checks

Aggregate checks can run without row-level keys when they have explicit metrics or aggregate definitions.

Grouped aggregates use `group_by` dimensions and should not treat those dimensions as row identity.

## Schema checks

Schema checks use adapter metadata.

Schema checks may inspect all columns, minus explicit schema ignore rules.

Schema checks should report ignored columns in evidence.

## CDC checks

CDC checks require explicit CDC configuration when behavior is ambiguous.

CDC checks should be small composable checks rather than one large opaque check.

## Failure details

Failure detail generation should be optional and bounded.

A check should be able to produce:

- summary only,
- limited failure rows,
- full failure output only when explicitly configured.

## Execution ordering

The planner should order checks so cheap and safety checks run first.

Recommended order:

1. metadata/schema checks,
2. freshness checks,
3. row count,
4. duplicate key checks,
5. key coverage checks,
6. aggregate checks,
7. row-level value checks.

## Design principle

The check engine should make every check result explainable, reproducible, and safe to trust.
