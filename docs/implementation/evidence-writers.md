# Evidence Writers

## Purpose

Evidence writers produce artifacts that explain what Recon checked, what assumptions were used, and what happened.

## Evidence writer responsibilities

Evidence writers should handle:

- terminal summaries,
- JSON run results,
- failure detail files,
- compiled artifact references,
- HTML reports,
- state references,
- sample key references.

Writers should distinguish local generated artifacts, result/evidence sinks,
and state:

- local artifact writers publish files under ignored paths such as `target/`
  and `reports/`,
- sink writers publish result or evidence records to explicit configured
  destinations after execution,
- state writers persist data that powers future runs, such as watermarks,
  previous-failure keys, or persisted sample keys.

Result/evidence sink placement is independent from execution placement. A check
may execute in one context and later write results elsewhere, but the sink must
not imply where the comparison ran.

## Writer boundaries

Check implementations should return structured data and artifact requests.

Evidence writers should handle file formats and paths.

Avoid writing files directly from deep check logic unless the check is explicitly producing a generated SQL file through the artifact layer.

Check logic should not write result tables, evidence tables, state files, or
failure-detail files directly. It should return structured outcomes and bounded
artifact or sink write requests for the appropriate writer layer.

Milestone 7.1 defines no generated evidence writer behavior. Milestone 8 owns
local run-result artifacts. Milestone 9 owns basic local evidence, reports, and
bounded failure details. Production table/result sinks belong to Post-MVP
Milestone 25.5 after sink schema, write semantics, privacy, and adapter
conformance are locked.

## Failure detail writer

Failure detail output should support:

- CSV initially,
- JSONL later,
- row limits,
- optional disabling,
- masking/redaction hooks later.

Suggested path:

```text
target/failures/{contract_name}__{check_name}.csv
```

Large failure-detail movement, JSONL, streaming, pagination, chunking, external
large-result stores, and writing large failure records through sink adapters are
Post-MVP Milestone 31 concerns unless a later split explicitly changes that
boundary. Failure-detail writers should prefer bounded files and references
over unbounded rows in memory or run-result artifacts.

## HTML report writer

The HTML report should summarize:

- run status,
- contract status,
- check results,
- sampling scope,
- tolerances,
- null rules,
- schema ignores,
- CDC mode,
- declared grain keys,
- declared CDC keys,
- blocked checks and their prerequisites,
- failure links,
- warnings and errors.

A simple static HTML report is enough at first.

Local HTML is an evidence writer, not a required proof side effect. Future
policy may allow local HTML to be disabled when table-backed or external
evidence is configured, unless a contract or run policy explicitly requires a
human-readable report.

## Result And Evidence Sink Writers

Future table-backed sinks may target the source connection, target connection,
or a third configured connection only when the sink destination is explicit and
the adapter declares compatible write/sink capabilities. Recon must not infer
sink destinations from available adapters.

Future sink modes may include terminal-only, local artifacts, table sink, both,
or disabled optional writers. Every configured sink must also define
requiredness and write status so a failed evidence write is distinguishable
from a failed reconciliation check.

Production table sinks need a separate schema/versioning and write contract
covering table creation policy, migration, append/upsert/merge behavior,
idempotency, retries, partial-write handling, retention, privacy, and links
back to local artifacts or state references.

## Terminal summary writer

Terminal output should be concise and readable.

Example:

```text
Compiled 8 checks for 2 contracts
PASS customer_revenue.row_count_diff
FAIL customer_revenue.revenue_by_month
```

## Sensitive data handling

Evidence, failure details, reports, run results, terminal output, logs, adapter
runtime errors, and test snapshots may contain source/target values or private
source/target context.

Before execution, runner/results, or evidence/reporting surfaces are
implemented, Recon should define a source/target data privacy policy that
classifies raw rows, comparison keys, normalized values, aggregate values, row
counts, relation names, query text, runtime adapter errors, and database error
text as public, sensitive, or policy-controlled.

Initial protections:

- do not emit raw source/target rows by default,
- limit failure rows,
- allow failure detail export to be disabled,
- prefer summaries and artifact references over embedded values,
- sanitize runtime adapter and database errors before public output,
- clearly document generated evidence paths.
- represent large or sensitive failure details with bounded samples and
  artifact/sink references rather than embedding rows in run results.

Future protections:

- masking,
- redaction,
- hash-only keys,
- sensitive column policies.

Serialized probabilistic summaries, Bloom-filter-like summaries, set sketches,
and intermediate probe outputs are sensitive or policy-controlled until a later
strategy proves safer handling. Candidate missing or extra records from a
probabilistic strategy must not be written as exact failure details or table
rows unless exact confirmation is required and performed.

## Full versus sampled

Every report should show whether each check ran on:

- full data,
- deterministic sample,
- incremental window,
- persisted random sample,
- previous failure set.

Sampled evidence should not imply full-data equivalence.

Every report should also show whether key-dependent checks used `grain.keys` or
`cdc.keys`, and should identify any CDC behavior intentionally not validated.

## Design principle

Evidence should make Recon trustworthy by showing assumptions, scope, and generated behavior.
