# Sampling Policies

## Purpose

This document defines sampling policies in Recon.

Sampling is a first-class concept because large datasets and continuous CDC pipelines often cannot run full row-level comparisons every time.

## Core principle

Sampling is a **policy**, not a single test option.

The same sampling strategy should be reusable across contracts.

## Sampling levels

Recon should support sampling at multiple levels.

### Contract-level default

```yaml
sampling:
  default_policy: stable_hash_5_percent
```

### Check-level override

```yaml
checks:
  - type: row_diff
    sampling: stable_hash_5_percent
```

### Check-pack override

```yaml
checks:
  use:
    - name: recon_core.cdc_equivalence
      sampling: latest_changed_records
```

### Full-data override

```yaml
checks:
  - type: sum_diff
    column: revenue
    sampling: full
```

Per-check overrides should win over contract defaults.

## Recommended location

```text
sample_policies/
  stable_hash_5_percent.yml
  latest_changed_records.yml
  previous_failures.yml
```

## Full data

`full` means no sampling filter is applied.

It is useful for row counts, aggregate totals, schema checks, and some key coverage checks.

## Deterministic hash

Purpose: always validate the same stable slice.

```yaml
name: stable_hash_5_percent
type: deterministic_hash
percent: 5
keys:
  inherit: contract.keys
```

Hash functions differ across databases. Recon must not assume hashes are portable across systems.

Safe approaches include persisted sample keys, sampling from source and applying keys to target, numeric modulo when valid, or adapter-declared portable hashing.

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

Important behavior:

- use last successful watermark,
- include lookback overlap for late-arriving records,
- advance watermark only after successful validation,
- require explicit bootstrap behavior for first run.

## Persisted random sample

Purpose: validate a random sample while ensuring source and target compare the same records.

```yaml
name: daily_random_10000
type: random_persisted
count: 10000
persist_keys: true
```

Random samples must persist keys. Random source and random target samples are not comparable unless the same keys are used.

## Previous failures

Purpose: retest records that failed recently.

```yaml
name: previous_failures
type: previous_failures
lookback_runs: 5
```

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

## Sampling and uniqueness

Sampling does not remove non-null or uniqueness requirements.

Any row-level value check still requires non-null and unique `grain.keys` in both source and target after sampling/windowing.

If null or duplicate keys are found in the sampled/windowed data, row-level checks should be blocked.

## Sampling and evidence

Sampling evidence should include policy name, mode, size, selected keys when appropriate, run id, timestamp window, watermark, lookback, compiled SQL or selection query, and whether the check ran full or sampled.

Reports must clearly state whether results are full-data or sampled.

## MVP recommendation

v0.1 should support full-data mode, deterministic hash or numeric modulo, incremental window design, and sample evidence model.

v0.2 should add persisted random and previous failures.

## Design principle

Sampling makes Recon useful for continuous validation, not only one-time comparisons. It must be explicit, reproducible, and visible in compiled artifacts.
