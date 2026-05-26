# Open Questions And Resolved Decisions

## Purpose

This document tracks unresolved product and implementation questions plus
resolved decisions that were originally tracked here.

Open questions should be resolved through design discussion, implementation learning, or ADRs when the decision becomes durable.

Entries marked `Decision` or `Locked by ADR` are not open questions. Future
agents should treat the referenced ADRs and framework docs as authoritative.

## Contract schema

### Should one file support multiple contracts in the first release?

Decision:

- support one contract per file,
- support multiple contract files in a project,
- support simple multi-contract YAML files,
- normalize all contracts into the same internal contract model.

### How should selectors and contract subset execution work?

Open.

Examples:

```bash
recon run --select tag:critical
recon run --select contract:customer_revenue
recon run --exclude tag:experimental
```

Preferred direction:

- use parsed manifest metadata, not raw file scanning,
- design selector syntax before implementation,
- define named selector shape in `selectors.yml`,
- define how `--select` and `--exclude` compose,
- record selected scope in compiled artifacts or run results when relevant,
- fail clearly when selectors match nothing unless an explicit empty-selection
  mode is added,
- resolve with a future ADR before dbt-like selectors or partial run behavior.

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

Decision:

- no for the current compiler design,
- explicit metrics compile into aggregate checks,
- numeric-column aggregate inference requires a future decision before it is
  enabled,
- see ADR 0015.

### What should happen when a check pack expands to nothing?

Decision:

- default to error,
- allow `on_empty: warn` or `on_empty: skip` later only when explicitly
  configured and visible in compiled artifacts,
- see ADR 0015 and ADR 0018.

## Columns and metrics

### Should undefined columns be allowed in checks?

Decision:

- if a contract has a `columns` block, checks and metrics should stay inside
  that declared surface,
- if no `columns` block exists, explicit checks and metrics may name columns
  directly and adapter metadata should validate existence/type,
- see ADR 0019.

### Should `columns.include: "*"` be supported?

Decision:

- yes later,
- never make it implicit,
- compile the actual resolved column list into artifacts,
- raw `*` must never appear in typed check plans,
- see ADR 0019.

### Should metrics require columns to be declared?

Decision:

- metrics may reference output columns directly,
- validation should confirm the referenced column exists and is type-compatible,
- metric columns must be declared only when the contract has an explicit
  `columns` block,
- see ADR 0019.

## Grain and uniqueness

### Should duplicate keys always block row-level checks?

Decision:

- yes for row-level value checks,
- aggregate checks may continue,
- `missing_keys` and `extra_keys` may still run as distinct non-null key coverage,
- any relaxed row-level matching behavior must be explicit and clearly marked unsafe or non-row-level,
- see ADR 0014.

### Should null key values be allowed?

Decision:

- null grain keys fail key safety checks,
- dependent row-level value checks are blocked,
- allow only with explicit advanced config later,
- see ADR 0014.

### Should CDC keys be separate from grain keys?

Decision:

- yes,
- `grain.keys` define comparison identity,
- `cdc.keys` define CDC/change propagation identity,
- they may be the same only when explicitly declared,
- see ADR 0014.

### How should advanced contracts model multiple identities?

Open.

Examples:

- order-level checks use `order_id`,
- line-level checks use `order_id, line_id`,
- CDC event checks use `event_id`,
- changed-row CDC checks use `order_id`.

Preferred direction:

- keep one default `grain.keys` and one default `cdc.keys` for simple
  contracts,
- add optional named identities for advanced contracts,
- let checks and check packs reference identity names,
- make check packs declare identity roles,
- have the compiler resolve references and write both references and resolved
  keys to compiled artifacts,
- reject unknown identities, wrong identity kinds, and missing required roles,
- resolve with a future ADR before multi-grain or multi-CDC-key execution.

## Sampling

### What deterministic sampling strategy is safest across systems?

Preferred direction:

- do not assume cross-database hash equality,
- prefer persisted sample keys or source-generated sample key sets,
- use numeric modulo only when key semantics allow it.

### How should sampling anchor side be modeled?

Open.

Some source or target systems may not efficiently generate sample keys. Recon
may need to generate sample keys from source, target, or an adapter-optimized
side, then apply those keys to both sides.

Preferred direction:

- support explicit anchor-side semantics before sampled row-level execution,
- consider values such as source, target, and either,
- persist or reference generated key sets when needed,
- expose the resolved anchor side in compiled artifacts and evidence,
- reject independent source and target samples for row-level comparison.

### How should first-run incremental windows work?

Preferred direction:

- require explicit bootstrap behavior,
- avoid silent full-history windows.

## Tolerances and normalization

### How should SQL Server empty string to Snowflake null be handled?

Locked by ADR 0009:

- strict by default,
- configurable through `nulls.treat_as_null` literal and limited regex
  sentinels at project, contract, column, and check level,
- compiled artifacts must show the resolved null policy.

### Should timezone policy be required for timestamp comparisons?

Locked by ADR 0009:

- timestamp tolerance execution is future gated,
- timestamp comparison must not silently convert timezones,
- missing timezone behavior is an error when conversion is required and
  metadata proves the ambiguity,
- unresolved metadata must be visible as deferred validation before evidence is
  trusted.

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

Decision:

- define explicit delete mode,
- require `cdc.keys` for delete propagation checks,
- compare key absence or delete operation evidence depending on mode,
- avoid one-size-fits-all CDC assumptions,
- allow `delete_mode: none` only when artifacts and evidence say delete propagation is not validated,
- see ADR 0014.

### How should asymmetric CDC delete representation be modeled?

Open.

Examples:

- source hard delete to target soft delete,
- source soft delete to target hard delete,
- source operation column to target soft delete.

Preferred direction:

- model source and target delete representation separately,
- define explicit public contract syntax before implementation,
- show both sides in compiled artifacts and evidence,
- validate unsupported combinations clearly,
- resolve this with a future ADR before CDC delete propagation checks.

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

- after the typed check-plan model, adapter API versioning, and shared adapter
  test kit are stable enough.

### Should Recon use dbt-style macro dispatch for dialect support?

Decision:

- no, not as the primary comparison engine.

Reason:

- core should own typed check plans and comparison semantics,
- adapters should render or execute typed operations,
- macro dispatch or SQL generation helpers can be internal implementation
  details later,
- see `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`.

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
