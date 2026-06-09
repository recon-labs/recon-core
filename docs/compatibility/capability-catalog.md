# Capability Catalog

## Purpose

Capabilities describe what an adapter can safely support.

They let Recon fail early when a check, typed operation, metadata request, or
artifact rendering step cannot be performed safely for a given system.

## Current status

The capability catalog is provisional.

Current state:

- capability names are documented in framework, architecture, and ADR docs,
- capability constants and support-state validation exist in code,
- the in-core DuckDB local development adapter declares the current
  relation-backed SQL rendering capability subset,
- no external production adapter declares capabilities yet,
- no adapter test kit validates capabilities yet.
- ADR 0021 defines future execution placement and materialization/staging
  capability needs, but those capability names are not implemented yet,
- ADR 0022 defines future result/evidence sink-write capability needs, but
  those capability names are not implemented yet.

## Capability rules

Capabilities must be:

- granular enough to prevent false portability,
- conservative by default,
- declared by adapters,
- validated by core when possible,
- tested by the shared adapter test kit once it exists,
- documented when their meaning changes.

Core owns the semantic decision about whether an operation may execute
side-locally, in one shared context, in Recon memory, in an adapter-managed
intermediate engine, or in a future external comparison engine. Adapter
capabilities can prove that the required mechanics exist; they do not let an
adapter redefine the reconciliation strategy Core planned.

An adapter must not claim a capability unless it implements and tests the
behavior. This is especially important for hash behavior, timestamp behavior,
null-safe equality, semi-structured projections, data movement, staging, and
result/evidence sink writes.

The future shared adapter test kit must include a SQL comparison conformance
matrix before external adapter repositories or adapter packages are split. That
matrix should prove declared comparison capabilities against null-safe equality,
distinct non-null key diff, nullable grouped aggregate keys, no implicit type
coercion, representative cross-type values, and unsupported-capability
diagnostics. It must explicitly test that key-diff type mismatches fail instead
of becoming misleading missing/extra rows, grouped aggregate key type
mismatches fail with adapter-level errors instead of raw dialect binder errors,
empty source/target relations with mismatched key types still fail, and grouped
aggregate renderers do not coalesce source and target group keys across
incompatible physical types. It must also test that aggregate input column and
value type mismatches fail instead of being compared through dialect implicit
casts, including boolean aggregate inputs on engines where `sum(boolean)` has
counting semantics and same-type unsupported or non-numeric aggregate metric
inputs that could otherwise surface raw dialect binder errors. It must also
cover valid exact numeric aggregate values, including large integers and
decimals, so adapter renderers cannot round or widen them through lossy casts.
Unsigned large-integer types such as DuckDB `UHUGEINT` must either be proven
exact for aggregate comparison or rejected with clear adapter-level errors.
The same matrix must also cover same-context rendering requirements when a
renderer cannot safely bridge multiple connection configs.

Unsupported required capabilities should produce clear diagnostics during
compile or validation when possible. Runtime-only capability failures should be
explicit and should not produce misleading evidence.

Capability support is represented by support state:

| Support state | Meaning |
| --- | --- |
| `unknown` | Adapter has not declared support. This never satisfies a required capability. |
| `unsupported` | Adapter intentionally does not support the capability. |
| `not_implemented` | Adapter is expected to support the capability later but does not yet. |
| `versioned` | Support depends on adapter, engine, or database version and must be checked. |
| `full` | Adapter implements and tests the capability. |

Required capabilities are satisfied only by `full`, or by `versioned` after the
version condition is validated.

Compile without an adapter may produce typed plans with
`rendering.status: not_rendered`. Adapter-aware rendering and runtime execution
must validate support states before rendering or executing required operations.
Malformed support-state values must become structured diagnostics instead of
uncaught adapter errors.

Milestone 6 uses only the capability subset required by currently emitted typed
operations. It does not expand the typed operation catalog.

## Draft capability names

These names are draft compatibility surfaces. They may change before the
adapter API is stable.

| Capability | Meaning |
| --- | --- |
| `relations` | Adapter can address named relations. |
| `queries` | Adapter can use authored queries as endpoints. |
| `metadata_columns` | Adapter can fetch column metadata; required for ADR 0019 all-column expansion. |
| `metadata_precision_scale` | Adapter can report precision and scale metadata where available. |
| `temp_tables` | Adapter can create or use temporary objects. |
| `cte_support` | Adapter can render common table expressions. |
| `row_count` | Adapter can count rows for a relation or query endpoint. |
| `aggregate` | Adapter can compute ungrouped aggregate comparisons. |
| `grouped_aggregate` | Adapter can compute aggregate comparisons segmented by group fields. |
| `key_diff` | Adapter can compare source and target key presence. |
| `null_key` | Adapter can detect rows where declared identity keys are null on one side. |
| `duplicate_key` | Adapter can detect duplicate keys for a side. |
| `null_safe_equality` | Adapter can compare values with explicit null semantics. |
| `numeric_cast` | Adapter can render safe numeric casts required by plans. |
| `string_cast` | Adapter can render safe string casts required by plans. |
| `timestamp_diff` | Adapter can compute timestamp differences with documented units. |
| `safe_hash_expression` | Adapter can hash values safely within one system. |
| `portable_hash_compatible` | Adapter hash behavior is intentionally compatible across systems and tested. |
| `json_path` | Adapter can address JSON or semi-structured paths. |
| `semi_structured_projection` | Adapter can project semi-structured data into comparable fields. |
| `schema_metadata` | Adapter can provide schema metadata required by schema checks. |

In Milestone 6, executable adapter-aware behavior is relation-only. The
`queries` capability is reserved for future executable query endpoint support
and is not required by current relation-only checks.

Future tolerance or normalization execution may require additional granular
capabilities after typed policy payloads are implemented. ADR 0009 locks
limited regex replacement as an MVP policy surface, so the implementation phase
must add a granular regex capability only when it also updates the code enum,
adapter docs, and tests.

## Future placement and sink capability families

The following capability families are planned compatibility surfaces. They are
not implemented capability constants today and must not be used by external
adapters as compatibility claims until the implementing milestone adds code,
tests, and adapter test-kit rows.

| Family | Candidate capabilities | Meaning |
| --- | --- | --- |
| Execution placement | `side_local_execution`, `same_context_execution`, `bounded_result_fetch` | Adapter can execute the planned operation in the location Core selected and return only the bounded result shape Core allowed. |
| Comparison placement | `same_context_comparison`, `external_comparison_engine` | Adapter or configured engine can compare source and target results in one approved context without adapter-owned semantic changes. |
| Materialization and staging | `temporary_staging_for_comparison`, `relation_extract`, `relation_load`, `table_to_table_copy` | Adapter can move, stage, or load data or summaries only under an explicit materialization policy with cleanup, privacy, and limits. |
| Result/evidence table writes | `table_create`, `table_migrate`, `table_append`, `table_upsert`, `table_merge`, `transactional_batch_write`, `table_metadata`, `temporary_staging_for_sink` | Adapter can write production result/evidence sink records with explicit schema, versioning, migration, idempotency, retry, and partial-write behavior. |

The final names may differ. The compatibility requirement is the same: unknown,
unsupported, `not_implemented`, malformed, or incompatible states do not satisfy
required execution, staging, comparison, or sink-write behavior.

## Hash compatibility warning

`safe_hash_expression` and `portable_hash_compatible` are different.

An adapter may safely hash values within one system without producing hashes
that are comparable across different systems. Cross-system hash compatibility
must not be assumed.

## Change rules

Capability changes affect compatibility when they:

- rename a capability,
- remove a capability,
- change capability meaning,
- change support-state semantics,
- make a capability required for an existing check,
- change diagnostics for unsupported capabilities,
- change which typed operations require a capability.
- change execution placement, comparison placement, materialization/staging, or
  sink-write capability semantics.

When a capability changes, update:

- this document,
- `docs/compatibility/typed-check-plan.md` when operation requirements change,
- `docs/compatibility/adapter-api.md` when adapter declarations change,
- `docs/compatibility/compatibility-matrix.md` when placement, staging, or sink
  compatibility status changes,
- adapter test-kit expectations once the test kit exists,
- relevant ADRs when the change is durable.

## Related docs

- `docs/framework/adapters.md`
- `docs/architecture/adapter-interface.md`
- `docs/implementation/adapter-interface-spec.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`
- `docs/decisions/adr-0022-evidence-privacy-failure-detail-and-result-sinks.md`
