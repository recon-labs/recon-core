# ADR 0022: Evidence Privacy, Failure Detail, and Result Sinks

## Context

Recon evidence explains what was checked, how it was checked, what assumptions
were used, and what happened. Evidence and results are public-output surfaces
once they are written to terminal output, generated artifacts, logs, reports,
tables, snapshots, or integrations.

ADR 0021 separates execution placement from sink placement. Execution placement
decides where checks run and where source/target results are compared. Sink
placement decides where outcomes, evidence, reports, failure details, state
references, or table records are written after execution.

Recon needs durable terminology before run-result and evidence phases implement
durable output, and before later phases add production result tables, advanced
stores, or external adapter packages. Without this boundary, a future
implementation could accidentally put environment-specific destinations in
contracts, treat result tables as state, make local HTML mandatory in every
environment, or leak sensitive source/target values through a secondary output.

Evidence and orchestration design has these constraints:

- local versioned artifacts should stay separate from persisted failure details,
- validation results, metadata stores, and human-readable reports should remain
  distinct surfaces,
- local/no-upload modes and failed-row samples need explicit controls,
- database result tables need explicit result handlers,
- small metadata channels and large payload storage need separate policies.

Recon should use explicit destinations, local-first artifacts, bounded detail
output, and store separation while preserving source-target reconciliation
semantics and fail-closed evidence.

## Decision

Recon will model results, evidence, and sinks with separate concepts:

| Term | Meaning |
| --- | --- |
| `RunResult` | Canonical in-memory run outcome object produced by execution. Writers and sinks consume it. |
| `CheckResult` | Canonical in-memory check outcome, including status, diagnostics, prerequisite/blocking metadata, and bounded values or references allowed by policy. |
| Local generated artifact | A file under ignored paths such as `target/`, `reports/`, or `state/`. |
| Result sink | A destination for run, contract, and check outcome records. |
| Evidence sink | A destination for reports, failure details, evidence metadata, and evidence links. |
| Result store | A durable result sink intended for querying or integration, such as production result tables. |
| State backend | Storage used to power future runs, such as watermarks, previous-failure keys, or persisted sample keys. State is not the same thing as evidence. |
| Sink placement | The destination where result or evidence records are written after execution. |

Execution placement and sink placement are independent. A check may execute in a
source database, target database, same-context adapter, Recon memory, or future
external comparison engine, then write results to local artifacts, a table sink,
both, or neither. Sink placement must not be used to infer where the check was
computed.

### Sink families

Recon will use these sink families:

| Family | Examples | Ownership |
| --- | --- | --- |
| Ephemeral/in-memory results | `RunResult`, `CheckResult` objects, test fixtures | First check-engine boundary may define internal shapes. |
| Terminal summary | Concise CLI result output | Run-result artifact phase. |
| Local run-result artifact | `target/run_results.json` | Run-result artifact phase. |
| Local evidence artifacts | `target/failures/`, `reports/`, evidence links | Basic evidence phase. |
| Local state artifacts | `state/`, sample-key files, watermark files | Local state phase. |
| Production result tables | `recon_runs`, `recon_check_results`, failure/evidence link tables | Production result-table phase. |
| Advanced evidence/result stores | Evidence vaults, templates, sign-off artifacts, JSONL/streaming large results | Advanced evidence/result-store phase. |
| Remote/database state backend | Shared production state tables or backend | Remote state-backend phase. |

Initial check-execution phases must not write run-result artifacts,
evidence artifacts, failure details, reports, production result tables, or
state.

### Sink modes

Future run policy may support these sink modes:

| Mode | Meaning |
| --- | --- |
| `terminal_only` | Print only a terminal summary; no durable result/evidence sink. |
| `local_artifacts` | Write local run-result and/or evidence artifacts under ignored paths. |
| `table_sink` | Write result/evidence records to configured tables. |
| `both` | Write local artifacts and table-backed records. |
| `disabled` | Disable a specific optional writer, such as a human report. |

No external upload, table sink, evidence vault, or remote service is enabled by
default. Every non-local sink must be explicitly configured and visible in run
metadata.

`target/run_results.json` remains the first durable machine-readable result
artifact in the run-result artifact phase. Later table-only enterprise modes may disable local
run-result writing only if the table sink carries equivalent invocation,
artifact-version, status, diagnostic, artifact-reference, and sink-write
metadata, and terminal output states that local run results were not written.

Local HTML reports are evidence writers, not proof that a run completed. A
future policy may disable local HTML when table-backed or external evidence is
configured, unless the contract or run policy explicitly requires a human
report.

### Destination ownership

Environment-specific sink destinations belong in project, profile, target, or
run-policy configuration. They do not belong directly in equivalence contracts
at first.

Equivalence contracts may later declare evidence requirements, such as:

- required evidence level,
- whether failure detail export is required,
- whether a human-readable report is required,
- whether a persistence class such as local artifact or durable store is
  required.

Contracts must not carry database credentials, vendor-specific table locations,
warehouse names, external vault URLs, or other environment-specific sink
destinations unless a later public schema decision explicitly adds that
capability.

Table-backed sinks may target:

- the source connection,
- the target connection,
- a third configured connection.

The destination must be explicit. Recon must not infer that source, target, or a
third connection should receive result tables because it happens to be available
or efficient.

### Requiredness and write status

Every configured sink must have explicit requiredness:

| Requiredness | Behavior |
| --- | --- |
| `required` | If the sink write fails, the run must surface an error and must not present evidence as complete. |
| `optional` | If the sink write fails, the run may warn only if the policy explicitly allows best-effort writes. |
| `disabled` | The writer is intentionally skipped, and run metadata should show that it was disabled when the surface would otherwise be expected. |

Sink-write status should be visible in future run metadata:

```text
not_configured
disabled
written
skipped
warning
failed
```

A failed required sink must be distinguishable from a failed reconciliation
check. The run should report both the check outcome and the evidence/write
failure without implying that missing evidence exists.

### Privacy defaults

Source/target values and private source/target context are sensitive by
default unless a later policy or configuration explicitly allows controlled
export.

Default classification:

| Data class | Default classification |
| --- | --- |
| Run/check status, diagnostic code, severity, and safe messages | Public. |
| Invocation IDs, artifact versions, adapter type, and non-secret writer status | Public. |
| Row counts, aggregate values, grouped keys, relation names, and source/target identifiers | Policy-controlled. |
| Raw rows, comparison keys, raw source/target values, normalized values, diff values, query text, database errors, rendered profile values, credentials, tokens, and DSN fragments | Sensitive. |
| Failure details, failed-row samples, sample keys, previous-failure keys, and CDC identifiers | Sensitive unless explicitly exported under policy. |

Terminal output, logs, diagnostics, run results, evidence artifacts, reports,
failure details, result tables, state references, and adapter test-kit
snapshots must use the same privacy rules. A value suppressed in one surface
must not leak through another.

Low-level parser, adapter, database, runtime, and evidence-writer exception
text must be summarized or sanitized before it reaches public output when it
can include authored YAML snippets, source/target query text, relation names,
row values, rendered profile values, credentials, DSN components, or private
engine payloads.

### Failure details

Failure details are a high-risk evidence surface.

The basic evidence phase may implement simple local failure details only after privacy
defaults, row limits, truncation behavior, and artifact references are locked.
CSV is the first local failure-detail format. JSONL, streaming, pagination,
external large-result stores, and richer failure-detail schemas remain
advanced evidence and large-result-store gate work.

Default failure-detail rules:

- Do not export raw rows by default.
- Do not export raw key values, raw source values, raw target values,
  normalized values, or diff values unless evidence policy explicitly allows
  that class.
- Apply row limits before writing detail files or table rows.
- Mark truncated detail explicitly in run results and evidence.
- Allow failure-detail export to be disabled.
- Prefer counts, statuses, safe diagnostics, and artifact references over
  embedded raw values.

### Result tables

Production result tables are a result store, not a state backend by default.

The production result-table phase owns:

- table schema and versioning,
- schema migration behavior,
- table creation policy,
- append versus upsert or merge semantics,
- idempotency and retry behavior,
- retention and deletion behavior,
- sink destination configuration,
- write capability requirements,
- partial-write behavior,
- links to local run results, evidence artifacts, failure details, and state
  records,
- privacy and masking behavior for table rows.

Result table implementation must wait until the run-result artifact and basic
evidence phases establish local semantics, and until local state shape is stable
enough to avoid confusing result tables with state tables.

Adapters must explicitly declare write/result-sink capabilities before Recon
writes production result tables through them. Candidate future capabilities
include:

```text
table_create
table_migrate
table_append
table_upsert
table_merge
transactional_batch_write
table_metadata
temporary_staging_for_sink
```

The final capability names and semantics belong to the adapter/capability docs
and future adapter test-kit work.

### State boundary

Evidence is for reviewing a run. State powers future runs.

Examples:

- A local failure CSV is evidence.
- A previous-failure key table is state.
- A `recon_check_results` table is a result store.
- A `recon_watermarks` table is state.

Local state belongs to local state work. Remote or database-backed state
belongs to remote state-backend work. Production result tables
must not silently become remote state.

## Phase Ownership

| Phase | Owns | Must not own |
| --- | --- | --- |
| First check-engine boundary | In-memory result/check-engine shape may reserve optional sink and artifact-reference fields. | No sink configuration, sink writes, run-result artifact, evidence, report, failure details, result tables, or state. |
| Row-count execution | Row-count execution may return in-memory outcomes and sanitized diagnostics. | No run-result/evidence sink writes. |
| Grain-key safety execution | Grain-key safety execution may return in-memory outcomes and prerequisite/blocking metadata. | No raw key export, failure detail sink, evidence sink, or state write. |
| Aggregate execution | Aggregate execution may return in-memory outcomes and sanitized bounded summaries allowed by privacy policy. | No run-result/evidence sink writes or grouped large-result export. |
| Run-result artifact | Terminal summary and local `target/run_results.json`. | No production result tables or advanced evidence stores. |
| Basic evidence | Basic local evidence, reports, failure details, truncation, and artifact references. | No production result tables unless explicitly re-split in planning docs. |
| Local state | Local state, watermarks, persisted sample keys, and previous-failure keys. | No remote/database-backed state. |
| Production result tables | Production result tables and write semantics. | No advanced evidence vault/templates/sign-off or remote state backend. |
| Adapter test kit and write/sink conformance | Adapter test kit and adapter write/sink capability conformance. | No adapter may claim sink compatibility without conformance. |
| Advanced evidence/result stores | Advanced evidence/result stores, JSONL/streaming large details, evidence vaults, templates, sign-off, richer redaction. | No basic evidence behavior should wait for these advanced surfaces. |
| Remote state backend | Remote/database-backed state. | Do not conflate with result tables. |

## Testing Strategy

Future implementation must add matrix-backed tests for:

- sink mode selection,
- required sink write failure,
- optional sink write warning behavior,
- disabled writer metadata,
- local-only, table-only, and both modes,
- source, target, and third-connection sink destinations,
- missing or unsupported adapter write capability,
- table schema/version mismatch,
- migration failure,
- retry and idempotency behavior,
- partial-write cleanup or failure reporting,
- retention and deletion policy,
- privacy leakage through terminal output, logs, run results, evidence,
  reports, failure details, result tables, state references, and test-kit
  snapshots,
- no generated run-result/evidence artifacts before their assigned milestones,
- adapter test-kit conformance for write/sink capabilities.

Every row must map to a test, an existing test, or an explicit out-of-scope
rationale before the corresponding implementation milestone starts.

## Alternatives Considered

### Put sink destinations directly in equivalence contracts

Rejected for the initial design.

Contracts define source-target equivalence. Sink destinations are environment
and operations choices. Mixing credentials or vendor-specific table names into
contracts would make contracts less portable and harder to review safely.

### Make local HTML reports mandatory

Rejected.

Human-readable reports are useful, but some production environments may use
machine-readable artifacts or table-backed stores instead. A report can be
required by policy, but it should not be an unskippable side effect.

### Treat result tables as state tables

Rejected.

Result tables support review, reporting, and automation. State controls future
run behavior. Some deployments may colocate them physically, but their
semantics, retention, migration, and safety rules are different.

### Default to uploading or externally storing evidence

Rejected.

Recon Core must not send results, metadata, failure details, or samples to an
external service by default.

### Auto-create production result tables whenever permissions allow

Rejected.

Table creation is a migration and ownership boundary. It requires explicit
schema/version, privilege, retention, idempotency, and migration behavior.

## Consequences

Result and evidence implementation will be staged, but the boundaries are clear
before code is written.

The first check-engine boundary can reserve internal shape for future sink metadata without
writing artifacts.

Milestones 8 and 9 can implement local results and basic evidence without
blocking on production table stores.

Enterprise-oriented result tables remain an explicit, gated capability rather
than an accidental side effect of adapter execution.

Future public docs must keep execution placement, sink placement, evidence, and
state separate.
