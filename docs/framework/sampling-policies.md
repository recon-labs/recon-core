# Sampling Policies

## Purpose

This document defines sampling policies in Recon.

Sampling is a first-class concept because large datasets and continuous CDC pipelines often cannot run full row-level comparisons every time.

## Core principle

Sampling is a **policy**, not a single test option.

The same sampling strategy should be reusable across contracts.

Example:

```yaml
sampling:
  policy: latest_changed_records
```

## Recommended location

```text
sample_policies/
  stable_hash_5_percent.yml
  latest_changed_records.yml
  previous_failures.yml
```

## Deterministic hash

Purpose: always validate the same stable slice.

```yaml
name: stable_hash_5_percent
type: deterministic_hash
percent: 5
keys:
  inherit: contract.keys
```

Use cases:

- repeatable baseline validation,
- debugging,
- large recurring checks.

Warning: database hash functions differ. Recon must not assume hashes are portable across systems. Safer approaches include persisted sample keys or numeric key modulo when valid.

## Incremental window

Purpose: validate records changed since the last successful run.

```yaml
name: latest_changed_records
type: incremental_window
timestamp_column: updated_at
watermark:
  source: recon_state
lookback: 2 hours
```

Use cases:

- CDC validation,
- scheduled source-to-target checks,
- near-real-time sync monitoring.

Important behavior:

- use last successful watermark,
- include overlap for late-arriving records,
- advance watermark only after successful validation.

## Persisted random sample

Purpose: validate a random sample while ensuring source and target compare the same records.

```yaml
name: daily_random_10000
type: random_persisted
count: 10000
persist_keys: true
```

Random samples must persist keys.

## Previous failures

Purpose: retest records that failed recently.

```yaml
name: previous_failures
type: previous_failures
lookback_runs: 5
```

This supports analyst-engineer fix loops and regression prevention.

## Stratified sample

Purpose: validate representation across groups.

```yaml
name: country_status_sample
type: stratified
strata:
  - country
  - status
per_group: 100
```

Likely post-MVP.

## High-value sample

Purpose: validate the most important records.

```yaml
name: high_value_transactions
type: priority
order_by:
  - column: amount
    direction: desc
limit: 1000
```

Likely post-MVP.

## Multi-policy sampling

Some contracts may need multiple sample sets:

```yaml
sampling:
  policies:
    - latest_changed_records
    - stable_hash_2_percent
    - previous_failures
```

Recon should design for this even if v0.1 supports one policy.

## Evidence

Sampling evidence should include:

- policy name,
- mode,
- size,
- selected keys when appropriate,
- run id,
- timestamp window,
- watermark,
- lookback,
- compiled SQL or selection query.

## MVP recommendation

v0.1 should support:

- deterministic hash or numeric modulo,
- incremental window design,
- sample evidence model.

v0.2 should add:

- persisted random,
- previous failures.

## Design principle

Sampling makes Recon useful for continuous validation, not only one-time comparisons.
