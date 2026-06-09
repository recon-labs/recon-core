# ADR 0021: Execution Placement and Comparison Engine Strategy

## Context

Recon compiles equivalence contracts into typed check plans. ADR 0013 keeps
reconciliation semantics in Core and lets adapters render or execute
system-specific mechanics. ADR 0020 defines the Milestone 6 adapter, profile,
and SQL rendering boundary, but deliberately stops before check execution.

Milestone 7 is split into:

- Milestone 7.1: check-engine boundary and in-memory result model,
- Milestone 7.2: row-count execution,
- Milestone 7.3: grain-key safety execution,
- Milestone 7.4: current aggregate metric execution.

Before any typed plan execution, Recon needs a durable execution-placement
policy. The same logical check can have different correctness, privacy,
performance, and evidence implications depending on where source operations,
target operations, comparison, materialization, and fallback behavior happen.

Mature tools provide useful reference points:

- dbt keeps database-specific behavior behind adapters and records adapter
  metadata in artifacts, but transformation macro dispatch is not Recon's
  comparison contract.
- Great Expectations and Soda separate result status from bounded detail and
  make high-volume detail explicit.
- Google Cloud Data Validation Tool shows why large source-target row
  comparison needs explicit keys, partitioning, and result handling.
- Airflow provider packaging shows that extension discovery is different from
  semantic compatibility.

Recon should borrow those boundaries while preserving its own rule: Core owns
source-target equivalence semantics, and adapters execute only the mechanics
Core has approved.

## Decision

Recon will model execution placement with three independent axes:

1. **Operation execution location**: where each source-side or target-side
   operation runs.
2. **Comparison location**: where source and target operation results are
   compared.
3. **Materialization and staging policy**: whether source or target data leaves
   its origin, where it is staged, what limits apply, and which adapter
   capabilities are required.

These axes are Core-owned semantics. Adapters may declare capabilities and
perform rendering, execution, metadata access, staging, and movement mechanics,
but adapters must not choose a different reconciliation strategy from the one
Core planned.

### Placement concepts

Recon will use these placement concepts in docs, plans, diagnostics, and future
result metadata:

| Concept | Meaning | First allowed use |
| --- | --- | --- |
| Side-local pushdown | Source operations run in the source context and target operations run in the target context. Recon compares only bounded returned results. | Row counts and small aggregate summaries when capability and privacy rules are satisfied. |
| Same-context pushdown | Source and target relations are addressable from one adapter execution context, so the comparison query can run in that context. | Current in-core DuckDB relation-backed execution. |
| Recon-local comparison | Recon Core compares returned values in process memory. | Only for explicitly bounded scalar or small structured results. |
| Adapter-managed intermediate engine | An adapter-managed engine stages data or summaries and performs comparison outside the original source or target. | Future gated work after staging, privacy, cleanup, and capability semantics are defined. |
| External comparison engine | A third configured connection acts as the comparison engine for staged source and target data or summaries. | Future gated work; not Milestone 7. |

These concepts describe execution and comparison placement only. Evidence or
result sinks are a separate decision surface. A run may execute in one location
and write results elsewhere later, but result/evidence sink placement does not
change where the check was computed.

### Fail-closed rules

Recon must prefer blocked or failed execution over misleading evidence.

Execution placement follows these rules:

- No execution milestone may silently fall back to Python when adapter SQL,
  adapter execution, engine capabilities, or placement requirements are
  unsupported.
- Recon-local comparison is allowed only for explicitly bounded results.
  Unbounded rows, large key sets, failure details, or grouped values must not be
  pulled into Core memory by default.
- Core must validate required adapter API versions and capabilities before
  execution. `unknown`, `unsupported`, `not_implemented`, malformed, or
  incompatible capability states do not satisfy required placement behavior.
- Adapters must not use dialect casts, hashes, collation, normalization, or
  timestamp behavior as hidden portability assumptions. Such behavior requires
  typed policy, declared capabilities, tests, and evidence visibility.
- Recon must not infer source-target mappings, grain keys, CDC keys, sampling
  anchors, or materialization anchors from adapter metadata.
- Any data movement, temporary object creation, staging table, extract,
  partitioning strategy, or intermediate-engine comparison must be explicit in
  the compiled plan or future run policy before execution.
- Diagnostics for unsupported placement must be structured, sanitized, and
  clear enough to explain why a check did not execute.
- Public output must not expose raw source/target rows, keys, relation data,
  query text, database error text, rendered profile values, or high-cardinality
  grouped results unless the relevant privacy and evidence policy permits it.

### Milestone ownership

Milestone 7.1 may define result/check-engine fields that leave room for future
placement metadata:

- planned operation execution location,
- planned comparison location,
- materialization policy status,
- required adapter capabilities,
- capability or placement blocker diagnostics,
- `not_executable` or `blocked` status reasons.

Milestone 7.1 must not execute adapters, query source/target systems, write
`target/run_results.json`, write evidence, write reports, emit failure details,
add public YAML placement syntax, or decide result/evidence sink placement.

Milestone 7.2 owns row-count execution placement. The first safe policy is:

- push source row count to the source side and target row count to the target
  side when both endpoints are supported by the selected adapter execution
  scope,
- compare only scalar counts in Recon Core,
- emit sanitized diagnostics for adapter/runtime failures,
- block unsupported query endpoints, cross-adapter execution, cross-context
  execution, and unbounded fallback.

Milestone 7.3 owns grain-key safety execution placement. It must preserve
`grain.keys` as comparison identity and must not infer keys or mappings.
Side-local null-key and duplicate-key summaries may be pushed down when
supported. Missing-key and extra-key comparison requires either same-context
pushdown or a later explicit materialization/intermediate-engine policy.
Recon-local key-set comparison is not allowed by default.

Milestone 7.4 owns aggregate metric execution placement for the current emitted
aggregate operations. Ungrouped scalar aggregates may use side-local pushdown
and bounded Recon-local comparison. Grouped aggregate comparison must not fetch
unbounded groups into Core memory. It requires same-context pushdown, explicit
bounded result limits, or a later materialization/intermediate-engine policy.

Milestone 8 owns durable run-result artifacts and may record placement and
capability metadata from executed checks. Milestone 9 owns evidence, reports,
failure details, and privacy policy for evidence output. Future milestones own
query endpoint execution, row-level value comparison, sampling execution, CDC
execution, adapter test-kit conformance, external adapter packages, and
external comparison engines.

## Placement Metadata Guidance

Future typed plans and results should be able to explain placement without
making unsupported behavior look executable.

Recommended field concepts:

```text
operation_execution_location
comparison_location
materialization_policy
required_capabilities
placement_status
placement_blockers
```

The exact schema belongs to the implementation milestone that emits the
machine-readable surface. Milestone 7.1 can define internal in-memory shapes,
but stable artifact fields belong to Milestone 8 or later.

## Testing Strategy

Each execution sub-milestone must add matrix-backed tests for:

- supported placement succeeds for the intended operation,
- unsupported placement blocks before execution,
- required adapter capability mismatch blocks before execution,
- Python fallback does not occur unless explicitly allowed and bounded,
- source/target values, raw rows, query text, database errors, rendered profile
  values, and high-cardinality details are not leaked,
- no run-result, evidence, report, failure-detail, state, or table-sink output
  is written before its assigned milestone,
- diagnostics preserve code, severity, safe message, path/resource context, and
  actionable hint where available.

Post-MVP adapter test-kit work must include SQL comparison conformance for
null-safe equality, key-diff semantics, grouped nullable keys, type mismatch,
aggregate empty-input behavior, unsupported capabilities, and dependency
installation behavior. Adapter package discovery or metadata is not sufficient
to claim execution compatibility.

## Alternatives Considered

### Always compare in Python

Rejected.

This would make early execution simple, but it could silently move sensitive or
large data into Recon Core, create unbounded memory behavior, and hide adapter
or dialect limitations.

### Always push every comparison into the source or target system

Rejected.

Some comparisons need both sides addressable in one context, and some source or
target systems cannot safely or portably execute every operation. A single
pushdown rule would either overclaim capability or require unsafe data
movement.

### Let adapters decide placement

Rejected.

Adapters know system mechanics, but Core owns reconciliation semantics. If
adapters choose placement independently, the same contract could mean different
things on different systems.

### Add user-facing YAML placement controls in Milestone 7.1

Rejected for Milestone 7.1.

The first task is to lock Core concepts and result boundaries. Public placement
syntax would affect contract schema, compatibility, evidence, privacy, and
adapter expectations, and it needs a separate design before implementation.

### Add an external comparison engine immediately

Rejected for Milestone 7.

External comparison engines are useful for enterprise-scale checks, but they
require explicit staging, cleanup, credential, privacy, capability, cost,
idempotency, and evidence semantics. The design keeps that path open without
pulling it into the MVP execution split.

## Consequences

Execution milestones will be narrower, but safer and easier to audit.

Core result and diagnostic models must represent blocked/not-executable checks
clearly.

Capability declarations become execution safety inputs, not only rendering
metadata.

Some useful scenarios will remain blocked until Recon has explicit
materialization, staging, privacy, and evidence policies. That is intentional:
blocked execution is safer than misleading evidence.

Future public docs must keep execution placement separate from evidence/result
sink placement.
