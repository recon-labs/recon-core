# ADR 0002: Equivalence Contracts as the Core Object

## Context

A reconciliation workflow needs more than isolated checks.

A team needs to define:

- what source output is compared,
- what target output is compared,
- how rows match,
- which values matter,
- which metrics matter,
- which differences are acceptable,
- which sampling policy is used,
- which schema differences are allowed,
- how CDC behavior is interpreted,
- what evidence is produced.

If these rules are scattered across scripts, the reconciliation logic becomes hard to understand and hard to trust.

## Decision

The primary user-authored object in Recon Core is the **equivalence contract**.

An equivalence contract defines the complete source-target comparison agreement.

Contracts should support:

- relation-based source and target,
- query-based source and target,
- grain and keys,
- columns,
- metrics,
- checks and check packs,
- sampling,
- tolerances and normalization,
- schema policy,
- CDC policy,
- evidence,
- severity,
- ownership,
- tags.

## Reasoning

A contract provides one durable place to understand a reconciliation agreement.

This makes Recon:

- easier to review,
- easier to rerun,
- easier to compile,
- easier to validate,
- easier to document,
- easier to extend.

A contract also gives the framework a clear public language that can be used by users, contributors, adapters, packages, and future integrations.

## Alternatives considered

### Tests as the main object

Tests are useful, but individual tests do not capture the full equivalence agreement.

### Pipelines as the main object

Pipelines are too broad. Recon should validate outputs, not become an orchestration framework.

### Tables as the main object

Tables alone are not enough because comparisons often use views, queries, business keys, metrics, and policies.

## Consequences

Implementation should treat contracts as the source of truth.

The compiler should normalize one-file-per-contract and multi-contract files into the same internal contract model.

User documentation should explain contracts before checks.
