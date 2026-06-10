# Evidence

## Overview

Evidence is the output that explains what Recon checked and what happened.

Evidence should show:

- source and target,
- checks run,
- sampling scope,
- tolerances,
- null/normalization rules,
- schema ignores,
- CDC mode,
- pass/fail/warn/error status,
- failure details where configured.

Current implementation writes manifest and compiled YAML artifacts. It also
writes compiled SQL when `recon compile --render-sql` succeeds for supported
adapter-backed checks. Run results, failure details, reports, and state outputs
are planned but not implemented yet.

Compiled SQL is not proof that checks ran. It is compile output that can be
inspected before execution.

## Current Machine-Readable Artifacts

```text
target/manifest.json
```

The manifest is useful for automation, CI, orchestration, and future
integrations.

## Current Human-Readable Artifacts

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/       # when recon compile --render-sql succeeds
```

Compiled artifacts explain what Recon will run. Compiled SQL is generated from
the rendered typed check plans; it is inspectable compile output, not evidence
that a check has executed.

## Planned Run Evidence

Future run and evidence generation should write:

```text
target/run_results.json
target/failures/
reports/
```

Run results and reports will explain what Recon did run.

`target/run_results.json` is planned as the first durable machine-readable run
result artifact. Basic local evidence, reports, and bounded failure details are
also future work. The current check-engine boundary only defines in-memory
check-engine/result behavior and does not write run results, evidence, reports,
failure details, result/evidence sinks, result tables, or state.

## Local Artifacts, Sinks, And State

Recon keeps local artifacts, result/evidence sinks, and state separate:

- local artifacts are generated files under ignored paths such as `target/` and
  `reports/`,
- result/evidence sinks are configured destinations for outcome or evidence
  records after execution,
- state powers future runs, such as watermarks, previous failures, and
  persisted sample keys.

Future sink modes may allow terminal-only output, local artifacts, table sinks,
both local and table output, or disabled optional writers. Non-local sinks must
be explicitly configured. Recon must not infer that source, target, or a third
connection should receive result tables just because that connection exists.

Local HTML reports are optional evidence writers in future policy terms. A
table-backed evidence or result sink does not automatically mean a local HTML
report was written, and a local HTML report does not imply table-backed
persistence.

## Failure details

Future failure details may be written under:

```text
target/failures/
```

Failure details may include sensitive source/target data. Future run results,
reports, terminal output, logs, adapter runtime errors, and test snapshots may
also expose source/target values or private source/target context if privacy
defaults are not defined.

Before those surfaces are implemented, Recon must define when raw rows,
comparison keys, normalized values, aggregate values, row counts, relation
names, query text, and runtime error text are public, sensitive, or
policy-controlled. Use row limits, disabling failure export, and
masking/redaction when available.

Failure detail output should be bounded and optional by default. Large failure
detail export, JSONL, streaming, pagination, chunking, and external large-result
stores are future advanced evidence work.

Future probabilistic key-diff strategies, such as Bloom-filter-like summaries
or other set sketches, require careful evidence wording. Candidate missing or
extra records from probabilistic strategies must not be presented as exact
failure details unless exact confirmation is required and performed.
Serialized summaries and intermediate probe outputs are sensitive or
policy-controlled until a later strategy proves safer handling.

## Full versus sampled evidence

Reports must say whether a check ran on:

- full data,
- deterministic sample,
- incremental window,
- persisted random sample,
- previous failure set.

Sampled results should not be presented as full-data equivalence.

## Truncation

If failure rows exceed the configured limit, the report should say so clearly.

## Evidence principle

Evidence should make the comparison trustworthy by showing assumptions, scope, and generated behavior.
