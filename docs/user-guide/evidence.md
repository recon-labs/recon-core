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

## Machine-readable evidence

Expected files:

```text
target/manifest.json
target/run_results.json
```

These are useful for automation, CI, orchestration, and future integrations.

## Human-readable evidence

Expected files:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
reports/
```

Compiled artifacts explain what Recon will run.

Reports explain what Recon did run.

## Failure details

Failure details may be written under:

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
