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

Current implementation writes manifest and compiled YAML artifacts. Run results,
failure details, reports, compiled SQL, and stateful evidence outputs are
planned but not implemented yet.

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
```

Compiled artifacts explain what Recon will run.

## Planned Run Evidence

Future run and evidence generation should write:

```text
target/compiled_sql/
target/run_results.json
target/failures/
reports/
```

Reports will explain what Recon did run.

## Failure details

Future failure details may be written under:

```text
target/failures/
```

Failure details may include sensitive data. Use row limits and masking/redaction when available.

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
