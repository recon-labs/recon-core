# Problem

## The practical problem

Data teams often need to prove that one dataset matches another.

Examples:

- Operational source data should match warehouse target data after CDC.
- Source tables should match warehouse landing tables after replication.
- Legacy warehouse and processing outputs should match modern warehouse outputs after modernization.
- Bronze, Silver, and Gold layers should preserve the expected data grain and totals.
- Old revenue logic should match rewritten revenue logic within acceptable tolerance.
- A new warehouse table should match the system it replaced before cutover.

This work is often called reconciliation, validation, QA, parallel-run testing, or source-target comparison.

## How teams do it today

Many teams still use ad hoc workflows:

```text
analyst writes SQL
analyst exports CSV
analyst compares manually
PM opens tickets
engineers fix logic
analyst reruns manually
evidence lives in spreadsheets, screenshots, Slack, and Jira
```

This creates problems:

- checks are not versioned,
- reruns are inconsistent,
- ownership is unclear,
- evidence is scattered,
- root cause is hard to track,
- cutover sign-off is fragile,
- teams repeat the same work across projects.

## Why normal data quality is not enough

Normal data quality checks are usually dataset-local:

- not null,
- unique,
- accepted values,
- row count greater than zero,
- freshness,
- schema checks.

These checks answer:

> Is this dataset internally healthy?

But they do not fully answer:

> Does this dataset match the source, old system, replicated table, or previous pipeline output?

A target table can pass data quality checks and still be missing records from the source.

## Why ingestion logs are not enough

CDC and ingestion tools can report success while target data is incomplete or stale.

Common failure modes:

- missed records,
- late-arriving changes,
- update/delete not applied correctly,
- schema drift,
- target transformation bug,
- precision or timestamp mismatch,
- partial backfill,
- stale medallion layer,
- wrong business-key mapping.

Recon is designed for the validation layer after or alongside data movement.

## Why one-off scripts are not enough

One-off reconciliation scripts work for a single urgent problem, but they do not scale.

They are hard to reuse because:

- every project invents its own format,
- sampling rules are inconsistent,
- evidence format differs,
- results are not comparable,
- test ownership is unclear,
- operational reruns are manual,
- contributors cannot easily understand the intent.

Recon turns those scripts into contracts, reusable checks, policies, and evidence.

## Why this is a recurring problem

The problem is not only migration.

It appears in recurring modern workflows:

- continuous CDC validation,
- warehouse replication,
- medallion-layer transformations,
- pipeline refactors,
- metric rewrites,
- system modernization,
- AI/ML feature source validation,
- regulatory reporting pipelines.

The more organizations depend on replicated and transformed warehouse data, the more they need a repeatable way to prove equivalence.

## What a good solution should provide

A good solution should let teams:

- define source and target datasets,
- define business keys / grain,
- define compare columns and tolerances,
- support existing compare views,
- support custom queries where needed,
- support deterministic and incremental sampling,
- run checks repeatedly,
- capture failures and evidence,
- integrate with CI or orchestration,
- keep logic in Git,
- generate sign-off artifacts.

This is the problem space Recon is designed to own.
