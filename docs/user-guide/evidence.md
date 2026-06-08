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
adapter-backed checks. Run results, failure details, reports, and stateful
evidence outputs are planned but not implemented yet.

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
