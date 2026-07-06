# Check Engine

## Purpose

The check engine executes compiled checks and returns structured results.

It should not parse authored YAML or resolve contract defaults. It receives
compiled checks and, when an execution stage needs contract metadata, matching
compiled-contract artifacts produced by compile.

It should execute typed check plans produced by core check planners. SQL
dialect rendering belongs to adapters.

## Inputs

Primary inputs:

```text
CompiledCheck
CompiledContract metadata
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

Implementation is split across check-engine stages. The first boundary owns the
check-engine boundary, status model, internal dispatch, and
prerequisite/blocking representation. The current row-count and grain-key safety
execution stages add relation-backed same-context DuckDB execution for the
supported `row_count_diff`, null-key, duplicate-key, missing-key, and extra-key
typed-plan shapes. A later aggregate execution stage adds execution for current
compiled aggregate metric typed-plan shapes. Execution stages must join each
executable compiled check to its matching compiled-contract metadata before any
profile, adapter, or query work starts.
`target/run_results.json`, evidence reports, failure details, and evidence links
remain separate later surfaces unless a later split explicitly changes those
boundaries.

The first boundary by itself is not an adapter execution lifecycle. It must not
load profiles, open source or target connections, instantiate runtime adapters,
render or execute SQL, query source or target systems, write
`target/run_results.json`, write evidence, emit reports, export failure details,
write state, write sink records, create materialized or staged data, or produce
probabilistic summaries. Any dependency slot for adapters, state, or evidence is
inactive unless the owning execution or writer phase explicitly activates it.

## First-boundary result metadata

The check engine may reserve in-memory metadata concepts that later stages use
to explain execution. Reserved metadata must be empty, not applicable, or
blocked until the owning phase implements the behavior.

Reserved concepts:

- planned operation execution location,
- planned comparison location,
- adapter or engine used,
- required capabilities and capability mismatch reason,
- blocked or not-executable reason,
- materialization or staging policy,
- exact, approximate, probabilistic, inconclusive, truncated, or
  confirmation-required result classification,
- artifact references,
- future result/evidence sink metadata.

These concepts must not create public YAML controls, stable public result
schema fields, adapter compatibility claims, or generated outputs by
themselves. A check that cannot satisfy its execution placement, adapter
capability, materialization policy, privacy rule, or result representation must
return an explicit blocker or not-executable reason with diagnostics. It must
not silently run in another location, fall back to Python, or present missing
execution as pass/fail evidence.

## Check interface

Each check implementation should declare:

- check type,
- required config,
- required contract context,
- required adapter capabilities,
- whether `grain.keys` are required,
- whether non-null and unique grain keys are required,
- whether `cdc.keys` are required,
- whether CDC ordering or windows are required,
- whether resolved concrete columns are required,
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

Null-key and duplicate-key failures should block row-level value checks that depend on unique matching.
Row-level value checks should not execute with unresolved wildcard selectors;
column resolution follows ADR 0019.

## Status model

Check statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

`pass`, `fail`, and `warn` require the check to have executed.

`fail` means the check ran and found an error-severity reconciliation
difference.

`warn` means the check ran and found a warning-severity reconciliation
difference.

`error` means Recon attempted to prepare or evaluate the check but a runtime,
compiled-artifact, internal, or unsafe-condition problem prevented a trustworthy
result.

`skipped` means the check was intentionally not run because explicit user,
configuration, or future selector policy said to skip it. Selector-driven skip
behavior is not implemented by the first check-engine boundary.

`blocked` means the check did not run because a prerequisite failed, errored,
was not executable, or was unavailable. Blocked results must include
`blocked_by` and a machine-readable reason.

`not_executable` means the compiled check is valid input to the run boundary
but cannot execute with the current check engine, typed operation, capability,
execution placement, materialization policy, or implemented operation surface.

`unsupported` and `not_yet_executable` are reason-code concepts, not statuses.
Unsupported check types, unsupported typed operations, missing capabilities,
unsupported placement, unsupported materialization, and behavior that belongs
to a later execution phase should produce `not_executable` with a structured
reason and diagnostics.

Known compiled check types or typed operations assigned to a later execution
phase should use reason `not_implemented_in_current_phase` and diagnostic
`RC_RUNTIME_CHECK_NOT_EXECUTABLE`. Validly shaped typed operations the runtime
does not recognize or support should use reason `unsupported_typed_operation`
and diagnostic `RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION`. Malformed typed
operation payloads are invalid compiled artifacts and should fail before
dispatch.

Every `blocked`, `not_executable`, or `skipped` result must set
`executed=false`, preserve safe diagnostics, leave source/target values empty,
and omit artifact, evidence, failure-detail, state, or sink references unless a
later owning phase actually produced them.

Run and contract aggregate statuses are defined by the result model. They must
not aggregate a run with only blocked, not-executable, errored, or empty check
sets to `pass`.

Empty compiled-check scope aggregates to `no_checks`. The first `RunService`
boundary maps that aggregate outcome to command-level runtime failure with
`RC_RUNTIME_NO_COMPILED_CHECKS`, not to success.

## Run service boundary

The `recon run` service uses already compiled check artifacts as input and joins
them to matching compiled-contract artifacts before any runtime profile or
adapter work. It should not parse authored YAML, recompile contracts, write
generated files, or run selector/subset logic.

For relation-backed row-count candidates and grain-key safety candidates that
match the supported typed plan shapes, the service may load the selected profile
and referenced profile connections, validate adapter metadata/API/capabilities,
open the supported adapter connection, classify scan-budget safety for key
checks, and pass an explicit execution context to the check engine. The current
key-safety path is allowed only when the internal local/dev scan guard
classifies the relation-backed input as bounded: the DuckDB database file must
be project-local and under the size cap, retained local DuckDB sidecars must be
absent, and the compiled source and target relations must resolve through
non-executing catalog metadata to local base tables. Retained sidecars, views,
externally backed relations, missing metadata, or metadata inspection failures
fail closed before adapter setup. The service must close adapters it opened. It
must not open adapters for checks that are not in the supported row-count or
bounded local/dev grain-key safety execution shapes, and
aggregate or row-level value checks must remain `not_executable` or blocked
until their owning execution phases exist.

Missing compiled-check artifacts, malformed compiled-check artifacts, and empty
compiled-check scopes are runtime diagnostics, not successful runs. They should
produce command-level failure through `ServiceResult` and should not claim
source-target equivalence.

Missing, malformed, or mismatched compiled-contract artifacts are runtime
diagnostics and must block before profile loading or adapter resolution.
Profile, adapter setup, adapter lifecycle, SQL execution, and cleanup failures
must produce sanitized diagnostics. No generated run-result, evidence, report,
failure-detail, state, or sink output is written by this execution boundary.

Command-level `ServiceResult` remains separate from `RunResult`. The CLI may
render a concise message and safe diagnostics, but final run summaries,
`target/run_results.json`, evidence tables, report links, failure-detail links,
state references, and sink destinations remain owned by later phases.

## Internal dispatch boundary

The first boundary may define an internal dispatch registry for already
compiled check types. This registry is an implementation detail for compiled
checks and is not a public authored check registry.

Unknown or unsupported compiled check types should produce
`not_executable` with reason `unsupported_check_type` and safe diagnostics.
Compiled checks whose typed operations are not executable in the current phase
should produce `not_executable` with reason
`not_implemented_in_current_phase`. Validly shaped unknown typed operations
should produce `not_executable` with reason `unsupported_typed_operation`.

The registry must not make explicit authored `checks: [...]`, package-provided
check implementations, or user-extensible check registration appear supported
before their public contract is designed.

## Failure details

Failure details should be optional and bounded.

A check may support:

- no failure detail,
- sampled failure detail,
- limited failure detail,
- full failure detail only when explicitly configured.

Current grain-key safety execution returns in-memory pass/fail outcomes,
failure counts, safe diagnostics, and prerequisite/blocking metadata only. It
does not export raw key values or write failure-detail artifacts.

## Row-level checks

Row-level value and row-matching checks require non-null and unique matching
keys.

If null or duplicate keys are present, value comparisons should not guess.

If null or duplicate key safety checks fail, dependent row-level value checks
should return status `blocked` with `blocked_by` and a machine-readable reason.

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

CDC propagation checks should use `cdc.keys`. CDC changed-row value checks may
also require `grain.keys` when they compare source and target row values.

## Design principle

The check engine should execute explicit compiled checks and return explainable structured results.
