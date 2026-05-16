# State and Watermarks

## Purpose

This document defines Recon state and watermarks.

State is essential for continuous CDC reconciliation, incremental validation, previous failure retesting, and reproducible sampling.

## What is state

State is information persisted across Recon runs.

Examples include last successful watermark, previous failed keys, sample keys, run history, check results, and evidence references.

## Watermark

A watermark tracks incremental progress.

Common types include timestamp, monotonically increasing id, CDC offset, batch id, load id, and ingestion time.

```text
last_successful_watermark = 2026-05-16T10:00:00Z
```

## Incremental window

An incremental window uses the previous watermark and current boundary.

```text
from: last_successful_watermark - lookback
to: current_watermark
```

Lookback helps catch late-arriving records.

## Bootstrap behavior

First-run behavior must be explicit.

Options may include requiring a start watermark, running a full initial comparison, using a configured bootstrap window, or failing until configured.

Recon should not silently start from “forever ago” unless configured.

## State update rule

A watermark should advance only after successful validation for the relevant contract and policy.

If checks fail, preserve the previous successful watermark unless configured otherwise.

## Late-arriving data

CDC data can arrive late.

Lookback overlap should be supported so records near the prior watermark are revalidated.

## Previous failures

Recon should store failed keys so future runs can retest them.

This powers `previous_failures` sampling.

## Sample key state

When sampling is random or generated from one side, sample keys should be persisted.

This ensures source and target compare the same records.

## CDC state

CDC checks may need state for last successful source timestamp, last successful target timestamp, last batch/load id, last CDC offset, previous delete checks, and previous failed keys.

## Local vs remote state

Local file state is useful for development and should live in gitignored `state/`.

Database state is useful for production.

Possible tables:

- `recon_runs`,
- `recon_check_results`,
- `recon_failure_details`,
- `recon_sample_keys`,
- `recon_watermarks`.

## State vs evidence

Evidence is for reviewing a run.

State is for powering future runs.

A failure CSV is evidence. A previous-failure key table is state.

## MVP recommendation

v0.1 can start with local artifacts.

v0.2 should add state for incremental windows, previous failures, and sample keys.

## Design principle

State turns Recon from a one-time comparison tool into a continuous validation framework.
