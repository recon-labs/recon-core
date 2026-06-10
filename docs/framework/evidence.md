# Evidence

## Purpose

This document defines evidence in Recon.

Evidence is a first-class output. Recon should not only return pass/fail; it should show what was checked, how it was checked, what assumptions were used, and what differed.

Evidence, run results, result sinks, and state are related but separate:

- local generated artifacts are files under ignored paths such as `target/`,
  `reports/`, and `state/`,
- result and evidence sinks are configured destinations that receive outcome or
  evidence records after execution,
- state powers future runs and is not evidence by default,
- execution placement does not decide sink placement.

The current check-engine boundary may define in-memory result/check-engine shape
only. It must not write run-result artifacts, evidence, reports, failure
details, result/evidence sinks, result tables, or state. `target/run_results.json`
belongs to the future run-result artifact phase. Basic local evidence, reports,
and bounded failure details belong to the future evidence phase. Production
result tables belong to later result-store work.

## Evidence types

### Terminal summary

Concise CLI output.

### Manifest

Machine-oriented parsed project graph:

```text
target/manifest.json
```

The manifest supports tooling, selectors, docs, compile, run, and CI workflows.

### Compiled contracts

Human-readable resolved contracts:

```text
target/compiled_contracts/customer_revenue.yml
```

### Compiled checks

Human-readable execution plan:

```text
target/compiled_checks/customer_revenue.yml
```

These should show check-pack expansion, metric expansion, columns used, sampling used, tolerances used, schema ignores, CDC mode, and delete behavior.

They should also show declared comparison identity, declared CDC identity, check requirements, generated safety checks, prerequisites, and blocking policy.

### Compiled SQL

Generated SQL should be available for debugging:

```text
target/compiled_sql/
```

### JSON run result

Machine-readable run outcome:

```text
target/run_results.json
```

This is the first durable machine-readable result artifact and remains future
work. It should reference generated artifacts or future sink records instead of
embedding large source/target values or failure rows.

### Failure details

Structured mismatch records:

```text
target/failures/customer_revenue__row_diff.csv
```

Fields may include run id, contract name, check name, key values, column name, source value, target value, normalized values, diff value, tolerance, and severity.

Failure details are optional, bounded, and privacy-controlled. They should not
export raw rows, raw keys, raw source/target values, normalized values, or diff
values unless policy explicitly allows that class of data. Row limits and
truncation markers must be applied before writing detail files or sink rows.

When tolerance, null, or normalization policy affects a value comparison,
failure details and reports should show the resolved policy. Evidence should
not imply that relative tolerance, timestamp tolerance, or string normalization
was applied unless the compiled check and adapter execution actually used that
resolved policy. When a string value becomes null because of
`nulls.treat_as_null`, evidence should show the sentinel rule that caused it
when evidence policy allows that detail.

For key safety checks, failure details may include bounded examples of null or duplicate keys when evidence settings allow them.

Future probabilistic key-diff strategies, such as Bloom-filter-like summaries
or other set sketches, must not present suspected missing or extra records as
exact failure details unless the strategy requires and performs exact
confirmation. Evidence must distinguish exact, approximate, probabilistic,
truncated, inconclusive, and confirmation-required outcomes.

### HTML report

Human-readable report:

```text
reports/customer_revenue.html
```

It should include run summary, contract metadata, source/target, checks, sampling, tolerances, null/normalization rules, schema ignore rules, CDC mode, failures, and evidence links.

Reports should also show which checks were blocked, which prerequisite checks blocked them, and whether each key-dependent check used `grain.keys` or `cdc.keys`.

### Result tables

Production teams may later persist result and evidence records in tables such
as `recon_runs`, `recon_check_results`, and evidence/failure-link tables.
Production result tables are result stores, not state backends by default.

Table-backed result/evidence sinks may target the source connection, target
connection, or a third configured connection only when the destination is
explicitly configured and the adapter declares compatible write/sink
capabilities. Recon must not infer a sink destination from available adapters.

Local HTML reports and local run-result artifacts are separate writers from
table sinks. A future policy may allow local artifacts only, table sinks only,
both, terminal-only output, or disabled optional writers, but each mode must be
explicit and visible in run metadata.

### Sample keys

When sampling is used, selected keys should be persisted where needed.

Persisted sample keys are state, not evidence by default. Evidence may
reference the persisted key set when policy allows it, but the state object
powers future runs and has separate retention and privacy requirements.

## Evidence levels

Possible levels are `summary`, `detailed`, and `debug`.

## Full versus sampled evidence

When a check uses an implemented sampling or window mode, reports must clearly
state whether it ran on full data, deterministic sample, incremental window,
random persisted sample, or previous failure set.

Sampled evidence should never imply full-data equivalence.

CDC evidence must also state when delete propagation is not validated, when CDC keys differ from comparison keys, and which window or ordering assumptions were used.

## Sensitive data

Failure details, run results, reports, terminal output, logs, adapter runtime
errors, and test snapshots can contain sensitive source/target values or private
source/target context.

Before check execution, runner/results, or evidence/reporting surfaces expose
source/target data, Recon must define privacy defaults for raw rows, comparison
keys, normalized values, aggregate values, row counts, relation names, query
text, and runtime error text. Those values should be emitted only when the
policy classifies them as public or explicitly allows controlled export.

Recon should support redaction, masking, hash-only keys, row limits, disabling
failure export, and sensitive column policies.

Serialized probabilistic summaries, Bloom filters, set sketches, and
intermediate probe outputs are sensitive or policy-controlled until a later
strategy proves safer handling. They can reveal information about source or
target key sets even when they do not contain raw rows.

## Failure row limits

If failure rows exceed configured limits, evidence should clearly say results were truncated.

Large failure-detail export, JSONL, streaming, pagination, chunking, external
large-result stores, and moving large failure rows from an execution engine to a
sink belong to advanced evidence/result-store work unless a future split
explicitly changes that boundary.

## Exit codes

Recon should return non-zero when error-severity checks fail.

Warnings may be configurable.

## Sequencing recommendation

Current compile behavior produces manifest, compiled checks/contracts, and
compiled SQL where supported. The first check-engine boundary should introduce
in-memory check results only.

The run-result artifact phase should add local run results. The basic evidence
phase should add local evidence, reports, and bounded failure details.

Later state work should add local state and persisted sample visibility. Later
result-store work should add production result table writing after state, result
table schemas, sink modes, and adapter write conformance are locked.

## Design principle

Evidence is part of the product, not a log side effect. Evidence should make assumptions, scope, and generated behavior visible.
