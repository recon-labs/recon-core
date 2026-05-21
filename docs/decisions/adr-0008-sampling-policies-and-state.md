# ADR 0008: Sampling Policies and State

## Context

Full row-level comparison can be expensive or unnecessary for every run.

CDC validation also needs incremental windows, watermarks, late-arriving data handling, previous failure retests, and reproducible samples.

Sampling can create misleading evidence if source and target samples are not aligned.

## Decision

Sampling is a first-class policy layer.

Sampling should be reusable, explicit, evidence-producing, and resolvable per check.

Supported sampling concepts include:

- full data,
- deterministic sample,
- incremental window,
- persisted random sample,
- previous failures,
- stratified sample later,
- high-value sample later.

Random sampling must persist keys.

Hash sampling must not assume cross-database hash equality.

Sampling that generates keys from one side must make that anchor side explicit
before execution. Recon must not independently sample source and target for
row-level comparison.

The exact public syntax for source-anchored, target-anchored, or
adapter-optimized sampling is not locked in this ADR. That needs a future
decision before sampled row-level execution or stable sampling artifact fields
are implemented.

## Sampling precedence

Sampling can be defined at multiple levels:

1. check-level override,
2. check-pack override,
3. contract default,
4. project default,
5. framework default.

## State

Recon should support state for recurring validation.

State may include:

- watermarks,
- previous failed keys,
- persisted sample keys,
- run history,
- check results.

Watermarks should advance only after successful validation for the relevant contract and policy.

## First-run behavior

Incremental windows need explicit bootstrap behavior.

Valid approaches may include:

- explicit start watermark,
- full initial comparison,
- configured bootstrap window,
- fail until configured.

Recon should not silently start from all history unless configured.

## Consequences

Sampling scope must appear in compiled artifacts and evidence.

Reports must say whether each check ran on full data, a deterministic sample, an incremental window, a persisted random sample, or previous failures.

When a sample is generated from one side, compiled artifacts and evidence must
show the sampling anchor side and key-set reference.

Sampled evidence must not imply full-data equivalence.
