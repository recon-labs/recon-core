# Check Engine Architecture

## Purpose

The check engine executes compiled checks and returns structured results.

The engine should be independent from the CLI and should interact with databases only through adapters.

## Inputs

The check engine receives:

```text
CompiledCheck
CompiledContract metadata
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

The check engine is introduced in split stages. The first boundary owns the
result status model, internal dispatch, and prerequisite/blocking
representation. Later execution phases add row count, grain-key safety, and
current aggregate metric execution. Execution phases that need source/target
metadata must consume compiled-contract artifacts rather than parsing authored
YAML or recompiling contracts. Run-result artifacts, evidence reports, failure
details, and evidence links remain separate later surfaces unless a future split
explicitly changes those boundaries.

The first check-engine boundary is not an execution phase by itself. It may
define internal dispatch and blocker metadata that later execution needs, but it
must not add public YAML placement syntax, generated run results, evidence
reports, failure-detail export, state, sink writes, materialization, or
probabilistic key-diff behavior.

The same boundary may reserve in-memory metadata for future execution and output
phases: operation execution placement, comparison placement, adapter or engine
used, required capabilities, capability mismatch, blocked or not-executable
reason, materialization policy, result classification, artifact references, and
future sink metadata. Reserved metadata is not a compatibility promise by
itself. It must remain empty, not applicable, or blocked until an owning phase
defines public field names, versioning, privacy behavior, and tests.

No-output behavior is part of the first boundary. A check result can state that
no adapter ran, no artifact was written, no evidence was produced, no failure
detail was exported, no state changed, and no sink write was configured or
attempted. It must not contain paths, table names, object locations, or sink
destinations that were not actually written by a later writer phase.

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

Placement decisions must be gate-backed per executable surface:

- row-count placement,
- grain-key safety placement,
- current aggregate metric placement,
- result artifacts, evidence, failure details, sinks, sampling, CDC, and
  advanced stores before those behaviors can execute.

The engine must represent placement or capability blockers explicitly. A check
that cannot satisfy its required execution context, materialization policy,
adapter capability, privacy rule, or result representation is `not_executable`
or blocked with a machine-readable reason; it is not rewritten into another
placement and is not silently executed in Core memory.

## Result semantics

Check outcomes use these statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

`pass`, `fail`, and `warn` require actual check execution. `error` records a
runtime, artifact, internal, or unsafe-condition problem that prevents a
trustworthy result. `blocked` records prerequisite dependency blocking.
`not_executable` records valid compiled checks that cannot run with the current
engine, typed operation, placement, capability, materialization, or implemented
surface. `skipped` is reserved for explicit user, configuration, or future
selector skip policy.

Unsupported and not-yet-executable checks are represented as
`not_executable` with machine-readable reason codes and safe diagnostics.
Reason codes, not status names, distinguish unsupported check type,
unsupported typed operation, missing engine capability, unsupported execution
placement, unsupported materialization policy, and behavior that belongs to a
later execution phase.

Known compiled check types or typed operations assigned to a later execution
phase use reason `not_implemented_in_current_phase`. Validly shaped typed
operations the runtime does not recognize or support use
`unsupported_typed_operation`. Malformed operation payloads are invalid compiled
artifacts and should fail before dispatch.

Run and contract aggregate results must never collapse incomplete execution to
`pass`. Empty check scopes, all-blocked checks, all-not-executable checks, and
errored check-engine preparation are explicit non-pass outcomes.
Empty compiled-check scope aggregates to `no_checks`; the first run service
boundary maps it to command-level diagnostic `RC_RUNTIME_NO_COMPILED_CHECKS`.

Command-level service results are separate from reconciliation results. The CLI
exit category and top-level message belong to command plumbing. `RunResult`,
`ContractResult`, and `CheckResult` carry reconciliation status, reason codes,
diagnostics, and future artifact or sink references.

The first non-executing run boundary may load already compiled checks and route
them through internal dispatch. The current row-count and bounded local/dev
grain-key safety execution boundaries may also load matching compiled-contract
metadata, selected runtime profiles, referenced connections, and supported
adapters for relation-backed same-context DuckDB `row_count_diff`, null-key,
duplicate-key, missing-key, and extra-key checks. They must still not parse
authored YAML, compile contracts, execute query endpoints, execute aggregate or
row-level value checks, write generated artifacts, emit evidence, mutate state,
write sinks, produce probabilistic summaries, or execute selector/subset scopes.
The bounded local/dev key-safety guard is stricter than DuckDB file size: it
also requires non-executing catalog metadata to show that both compiled relation
endpoints are local base tables in the project-local DuckDB file.

## Adapter capability fit

Checks declare required semantics. Core translates those semantics into typed
operations and required capabilities. Adapters report available mechanics.

The check engine must validate capability fit before execution starts. Capability
states such as `unknown`, `unsupported`, `not_implemented`, malformed, or
incompatible do not satisfy required behavior. A missing or inadequate
capability is a structured blocker, not permission to use a fallback strategy.

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
and returned as `blocked` with `blocked_by` and a machine-readable reason.
Row-level value checks should not execute with unresolved wildcard selectors;
column resolution follows ADR 0019.

Row-level value checks also should not execute with unresolved tolerance, null,
or normalization policy. Policy resolution follows ADR 0009, and adapter
capability validation must happen before rendering policy-dependent typed
operations, including limited regex replacement.

Future key-diff strategies may include exact same-context key comparison or
probabilistic summaries such as Bloom filters or set sketches. Exact key
comparison is preferred when safe placement exists. Probabilistic strategies
must not be introduced as hidden optimizations; they require explicit
false-positive semantics, partition or window scope, deterministic composite-key
serialization, bidirectional probing when both missing and extra coverage are
needed, privacy classification for serialized summaries, and exact-confirmation
rules before failure rows or sink records are presented as concrete missing or
extra records.

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

Large failure details should not be embedded directly in `CheckResult` or a
future run-result artifact. Future sink-backed evidence may write large details
to a configured source, target, or independent sink adapter only after sink
placement, schema versioning, idempotency, retention, privacy, and adapter write
conformance are defined. Until then, failure rows remain bounded samples or
references to explicitly generated local artifacts.

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
