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

Milestone 7 introduces the check engine in split stages. Milestone 7.1 owns the
boundary, result status model, internal dispatch, and prerequisite/blocking
representation. Milestone 7.2 starts execution with row count, Milestone 7.3 adds
grain-key safety execution, and Milestone 7.4 adds current aggregate metric
execution. Run-result artifacts remain Milestone 8, and evidence reports,
failure details, and evidence links remain Milestone 9 unless a later split
explicitly changes those boundaries.

## Check lifecycle

Recommended lifecycle:

```text
validate check requirements
prepare execution
produce or load typed check plan
ask adapter to render SQL or execution request
execute
collect result values
collect failure details when configured
return CheckResult
```

## Execution placement

Before executing typed plans, the check engine must decide where each
comparison is allowed to run:

- source system,
- target system,
- adapter-managed intermediate system,
- bounded Python-side comparison inside Recon Core.

The default direction is database pushdown through adapter-rendered SQL where
that is safe and supported. Core owns the semantic strategy and typed plan.
Adapters own system-specific rendering and execution.

Unsupported SQL rendering must not silently fall back to Python. Python-side or
intermediate-system comparison requires explicit limits, diagnostics, privacy
rules, result semantics, and evidence visibility before implementation.

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
- whether non-null or unique grain keys are required,
- whether CDC keys are required,
- whether CDC ordering or windows are required,
- whether resolved concrete columns are required,
- supported sampling modes,
- result schema.

Checks should not hide comparison semantics in adapter-specific SQL strings.
They should produce typed plan operations that adapters can render or execute.

## Row-level checks

Row-level checks require `grain.keys`.

Value-level row checks require non-null and unique keys in source and target.

Null-key and duplicate-key checks should run before row-level value checks.

If null keys or duplicates are found, row-level value checks should be blocked
and returned as `skipped` with `blocked_by` and `skip_reason`.
Row-level value checks should not execute with unresolved wildcard selectors;
column resolution follows ADR 0019.

Row-level value checks also should not execute with unresolved tolerance, null,
or normalization policy. Policy resolution follows ADR 0009, and adapter
capability validation must happen before rendering policy-dependent typed
operations, including limited regex replacement.

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

CDC propagation checks should use `cdc.keys`. CDC changed-row value checks may
also require `grain.keys` when they compare source and target row values.

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
