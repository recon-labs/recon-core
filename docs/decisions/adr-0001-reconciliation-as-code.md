# ADR 0001: Reconciliation as Code

## Context

Data teams often need to prove that two data outputs are equivalent.

Examples include:

- source database versus warehouse replica,
- old warehouse output versus new warehouse output,
- Spark output versus Snowflake output,
- Bronze layer versus Silver layer,
- old business metric versus new business metric,
- CDC stream versus target table.

This work is often handled with one-off SQL, spreadsheets, screenshots, manual analyst QA, Slack threads, and tickets. The logic is difficult to review, difficult to rerun, and difficult to reuse.

## Decision

Recon Core uses **Reconciliation as Code** as its core product model.

Reconciliation logic should be:

- versioned,
- reviewable,
- executable,
- repeatable,
- reusable,
- evidence-producing.

Recon should let users define source-target equivalence in files, run checks through a CLI, and generate artifacts that explain what happened.

## Reasoning

Reconciliation is not only a query execution problem. It is an engineering workflow.

The framework needs to support:

- explicit contracts,
- standard checks,
- reusable policies,
- parse and compile behavior,
- generated evidence,
- CI and orchestration usage,
- repeatable validation after fixes.

A code-first model fits engineering teams that already use Git, pull requests, CI, dbt, Airflow, and data platform workflows.

## Alternatives considered

### One-off SQL helper

A helper that only generates SQL would be easier to build, but it would not define a durable product category or solve evidence, reuse, validation, and workflow problems.

### Hosted application first

A hosted UI could be valuable later, but it would slow down the core open-source framework and make the product less developer-native at the beginning.

### Generic data quality framework

A generic data quality tool would dilute the focus. Recon should be centered on source-target equivalence, not every possible assertion.

## Consequences

Recon Core should prioritize:

- files over UI-first configuration,
- CLI over hosted workflow first,
- contracts over isolated tests,
- evidence over screenshots,
- explicit validation over convenience magic.

Docs, examples, and implementation should consistently reinforce the Reconciliation as Code model.
