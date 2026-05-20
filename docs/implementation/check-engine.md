# Check Engine

## Purpose

The check engine executes compiled checks and returns structured results.

It should not parse authored YAML or resolve contract defaults. It receives compiled checks.

It should execute typed check plans produced by core check planners. SQL
dialect rendering belongs to adapters.

## Inputs

Primary inputs:

```text
CompiledCheck
ExecutionContext
AdapterRegistry
StateBackend
EvidenceWriter
```

## Outputs

Primary outputs:

```text
CheckResult
FailureDetail references
EvidenceArtifact references
Diagnostics
```

## Check interface

Each check implementation should declare:

- check type,
- required config,
- required contract context,
- required adapter capabilities,
- whether `grain.keys` are required,
- whether unique keys are required,
- whether columns are required,
- supported sampling modes,
- result fields,
- failure detail support.

Illustrative interface:

```python
class Check:
    type: str

    def requirements(self) -> CheckRequirements: ...
    def plan(self, compiled_check: CompiledCheck, context: PlanningContext) -> CheckPlan: ...
    def execute(self, plan: CheckPlan, context: ExecutionContext) -> CheckResult: ...
```

## Check registry

Checks should be resolved through a registry.

```python
registry.get("row_count_diff")
registry.get("sum_diff")
```

The registry should support built-in checks first and package-provided checks later.

## Check planning

Planning should happen before execution.

A planned check may include:

- typed source operations,
- typed target operations,
- typed comparison operations,
- optional rendered SQL artifact references,
- failure detail operations,
- required adapters,
- expected result schema.

Typed operations are the core contract. Rendered SQL is an adapter-specific
execution artifact.

## Execution order

Recommended order:

1. schema and metadata checks,
2. freshness checks,
3. row count,
4. duplicate key checks,
5. key coverage checks,
6. aggregate checks,
7. row-level value checks.

Duplicate key failures should block row-level value checks that depend on unique matching.

## Status model

Check statuses:

```text
pass
fail
warn
error
skipped
```

`fail` means the check ran and found mismatches.

`error` means the check could not run.

`skipped` means the check was intentionally not run because a prerequisite failed or configuration said to skip.

## Failure details

Failure details should be optional and bounded.

A check may support:

- no failure detail,
- sampled failure detail,
- limited failure detail,
- full failure detail only when explicitly configured.

## Row-level checks

Row-level checks require unique matching keys.

If duplicate keys are present, value comparisons should not guess.

## Aggregate checks

Aggregate checks compare summarized values and may not need row-level keys.

Metric-based aggregate checks should preserve metric names in results and evidence.

## Schema checks

Schema checks use adapter metadata.

They should respect schema policies and report ignored columns.

## CDC checks

CDC checks should be small and composable.

Examples:

- freshness lag,
- latest window count,
- operation count diff,
- delete propagation,
- previous failure retest.

## Design principle

The check engine should execute explicit compiled checks and return explainable structured results.
