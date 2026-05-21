# Sampling Engine

## Purpose

The sampling engine resolves sampling configuration into executable sampling behavior for each check.

## Inputs

Inputs:

- compiled contract,
- compiled check,
- sampling policies,
- state backend,
- adapter capabilities.

## Outputs

Outputs:

- resolved sampling mode,
- sampling predicate or key set,
- sample evidence metadata,
- state updates when appropriate.

## Sampling modes

Supported design targets:

```text
full
deterministic_hash
numeric_modulo
incremental_window
random_persisted
previous_failures
stratified
priority
```

## Full mode

No sampling predicate is applied.

Use for:

- row counts,
- aggregate totals,
- schema checks,
- full value checks.

## Deterministic hash

Deterministic hash sampling must not assume cross-database hash equality.

Valid approaches:

- portable hash supported by both adapters and tested,
- sample keys generated once and applied to both sides,
- numeric modulo when key semantics allow it.

## Numeric modulo

Numeric modulo can be safe when keys are numeric, stable, and comparable.

Example:

```text
customer_id % 100 < 5
```

This should not be used for non-numeric or non-stable keys.

## Incremental window

Incremental windows use watermarks.

Resolved window:

```text
from = last_successful_watermark - lookback
to = current_boundary
```

First-run behavior must be explicit.

## Random persisted

Random sampling must persist selected keys.

Randomly sampling source and target independently is invalid for row-level comparison.

## Previous failures

Previous failure sampling reads failed keys from state and retests them.

This requires state support.

## Per-check resolution

Sampling precedence:

```text
check-level
check-pack-level
contract-level
project-level
framework default
```

Each compiled check should have resolved sampling.

## Uniqueness

Sampling does not remove row-level non-null or uniqueness requirements.

Row-level checks must validate unique keys within the sampled/windowed data.

## Evidence

Sampling metadata should include:

- sampling mode,
- policy name,
- filter/window,
- sample size,
- key set reference when relevant,
- state reference when relevant.

## Design principle

Sampling must be reproducible, explicit, and honest about scope.
