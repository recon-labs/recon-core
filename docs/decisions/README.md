# Architecture Decision Records

This directory contains durable product and architecture decisions for Recon Core.

Decision records are used when a choice affects public behavior, contributor expectations, contract syntax, artifact formats, adapter interfaces, package structure, or validation rules.

## How to use this directory

Read these records before changing:

- contract syntax,
- parse, compile, or run behavior,
- generated artifact formats,
- check-pack behavior,
- validation rules,
- adapter interfaces,
- package loading,
- evidence outputs.

## Decision record format

Each record should explain:

- the context,
- the decision,
- the reasoning,
- alternatives considered,
- consequences,
- implementation guidance.

Decision records should be updated only when the project intentionally changes direction. If a decision is replaced, create a new record and link the older one rather than rewriting history silently.

## Current records

```text
adr-0001-reconciliation-as-code.md
adr-0002-equivalence-contracts-as-core-object.md
adr-0003-parse-compile-run-artifact-model.md
adr-0004-columns-metrics-checks-semantics.md
adr-0005-strict-validation-and-no-silent-magic.md
adr-0006-contract-compiler-validation-rules.md
adr-0007-grain-keys-and-row-level-uniqueness.md
adr-0008-sampling-policies-and-state.md
adr-0009-tolerance-normalization-and-null-equivalence.md
adr-0010-schema-policies-and-technical-columns.md
adr-0011-cdc-policy-and-delete-modes.md
adr-0012-adapter-and-package-ecosystem.md
adr-0013-typed-check-plans-and-adapter-sql-rendering.md
adr-0014-key-semantics-and-check-dependencies.md
```
