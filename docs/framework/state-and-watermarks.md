# State and Watermarks

## Purpose

This document defines Recon state and watermarks.

State is essential for continuous CDC reconciliation, incremental validation, previous failure retesting, and reproducible sampling.

## What is state

State is information persisted across Recon runs.

Examples include last successful watermark, previous failed keys, persisted
sample keys, CDC offsets, and state references to prior runs.

State is separate from evidence and result stores:

- evidence explains a completed run,
- result stores support review, reporting, and integrations,
- state controls future run behavior.

Milestone 7.1 through 7.4 must not write state. Local state belongs to Post-MVP
Milestone 25. Production result tables belong to Post-MVP Milestone 25.5 and
must not silently become state tables. Remote or database-backed state belongs
to Post-MVP Milestone 37.

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

Recon should not silently start from "forever ago" unless configured.

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

Sample-key state should record which side generated the keys when sampling is
anchored on source or target. The public syntax for sampling anchor side is not
locked yet and should be decided before sampled row-level execution.

## CDC state

CDC checks may need state for last successful source timestamp, last successful target timestamp, last batch/load id, last CDC offset, previous delete checks, and previous failed keys.

State that stores previous failures, sample keys, or CDC windows should record which identity was used: comparison identity from `grain.keys` or change identity from `cdc.keys`.

## Local vs remote state

Local file state is useful for development and should live in gitignored `state/`.

Database state is useful for production.

Possible tables:

- `recon_sample_keys`,
- `recon_watermarks`.

Result tables such as `recon_runs`, `recon_check_results`, and
`recon_failure_details` are result/evidence stores by default, not state. A
future deployment may colocate result and state tables physically, but the
schemas, retention rules, update rules, idempotency behavior, privacy policy,
and adapter capabilities must remain separate.

## State vs evidence

Evidence is for reviewing a run.

State is for powering future runs.

A failure CSV is evidence. A previous-failure key table is state. A production
`recon_check_results` table is a result store unless a later state-backend
design explicitly gives it state semantics.

Serialized probabilistic summaries, Bloom-filter-like summaries, set sketches,
and intermediate probe outputs should not be treated as harmless state or
evidence by default. Until a future strategy classifies them, they are sensitive
or policy-controlled because they may reveal information about source or target
key sets. If they are retained across runs, the state design must define scope,
retention, cleanup, privacy, and exact/probabilistic result semantics.

## Milestone recommendation

v0.1 can start with local generated artifacts and no stateful run behavior.

v0.2 should keep state, watermark, previous-failure, and sample-key behavior at
the design/gate level where needed. v0.3 / Post-MVP Milestone 25 should add
local state for incremental windows, previous failures, persisted sample keys,
and watermark advancement. Production result tables should be handled in
Post-MVP Milestone 25.5, and remote/database state should remain separate until
Post-MVP Milestone 37.

## Design principle

State turns Recon from a one-time comparison tool into a continuous validation framework.
