# Open Questions

## Purpose

This document tracks unresolved product and implementation questions.

Open questions should be resolved through design discussion, implementation learning, or ADRs when the decision becomes durable.

## Contract schema

### Should one file support multiple contracts in the first release?

Preferred direction:

- support one contract per file first,
- support multiple contracts per file if it does not delay the parser,
- normalize both into the same internal contract model.

### How much inheritance should contracts support?

Preferred direction:

- support project/file defaults,
- support named reusable resources,
- defer deep contract inheritance/templates until repetition proves it is needed.

### Should endpoint refs be included early?

Preferred direction:

- design for endpoint refs,
- implement after basic relation-based contracts are stable.

## Query support

### Should custom source/target queries be implemented in the first release?

Preferred direction:

- include query support in the schema and docs,
- implement relation-first execution first,
- add query execution early because surrogate-key and canonical-output cases are central to real reconciliation.

## Check packs

### Should check packs infer aggregate checks from numeric columns?

Preferred direction:

- allow only if documented,
- make expansion visible in compiled artifacts,
- prefer explicit metrics for business-important aggregates.

### What should happen when a check pack expands to nothing?

Preferred direction:

- default to error,
- allow `on_empty: warn` or `on_empty: skip` later only when explicitly configured.

## Columns and metrics

### Should undefined columns be allowed in checks?

Preferred direction:

- no, fail validation unless the check explicitly supports expressions.

### Should `columns.include: "*"` be supported?

Preferred direction:

- yes later,
- never make it implicit,
- compile the actual resolved column list into artifacts.

### Should metrics require columns to be declared?

Preferred direction:

- metrics may reference output columns directly,
- validation should confirm the referenced column exists and is type-compatible,
- docs should explain whether metric columns must also appear under `columns`.

## Grain and uniqueness

### Should duplicate keys always block row-level checks?

Preferred direction:

- yes by default,
- aggregate checks may continue,
- any relaxed behavior must be explicit and clearly marked unsafe or non-row-level.

### Should null key values be allowed?

Preferred direction:

- default to error for row-level checks,
- allow only with explicit advanced config later.

## Sampling

### What deterministic sampling strategy is safest across systems?

Preferred direction:

- do not assume cross-database hash equality,
- prefer persisted sample keys or source-generated sample key sets,
- use numeric modulo only when key semantics allow it.

### How should first-run incremental windows work?

Preferred direction:

- require explicit bootstrap behavior,
- avoid silent full-history windows.

## Tolerances and normalization

### How should SQL Server empty string to Snowflake null be handled?

Preferred direction:

- strict by default,
- configurable via null policy at project, contract, column, and check level,
- compiled artifacts must show the resolved null policy.

### Should timezone policy be required for timestamp comparisons?

Preferred direction:

- warn initially when missing,
- require explicit timezone behavior in strict mode.

## Schema policies

### Should schema checks fail on target-only CDC columns?

Preferred direction:

- yes by default,
- support explicit target ignore lists and patterns,
- report ignored columns in evidence.

### Should type compatibility use logical or physical types?

Preferred direction:

- use adapter-normalized logical compatibility,
- preserve physical type details in evidence.

## CDC

### Which CDC modes should be implemented first?

Preferred direction:

- timestamp-window/upsert style first,
- operation-column and soft-delete support next,
- tombstone and SCD2 later.

### How should hard delete validation work?

Preferred direction:

- define explicit delete mode,
- compare key absence or delete operation evidence depending on mode,
- avoid one-size-fits-all CDC assumptions.

## Evidence

### How much failure detail should be exported by default?

Preferred direction:

- store limited failure details,
- cap rows,
- make limits visible,
- add masking/redaction later.

### Should HTML reports be included in the first release?

Preferred direction:

- simple report if cheap,
- JSON and terminal evidence are more important initially.

## Adapters

### Which adapter should be first?

Preferred direction:

- use a local/test-friendly adapter for development,
- prioritize Postgres/Snowflake paths based on real use,
- keep adapter interface stable before splitting many repos.

### When should adapter packages split from `recon-core`?

Preferred direction:

- after the adapter interface and test kit are stable enough.

## Packages and Hub

### When should `recon deps` be implemented?

Preferred direction:

- after local packages/check packs are useful,
- before Hub becomes important.

### When should Recon Hub exist?

Preferred direction:

- after official packages and adapters exist,
- start as a static index repo.

## Decision process

When an open question affects public schema, artifact format, adapter interface, or validation behavior, resolve it with an ADR.
