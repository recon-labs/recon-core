# Capability Catalog

## Purpose

Capabilities describe what an adapter can safely support.

They let Recon fail early when a check, typed operation, metadata request, or
artifact rendering step cannot be performed safely for a given system.

## Current status

The capability catalog is provisional.

Current state:

- capability names are documented in framework, architecture, and ADR docs,
- no stable capability constants exist in code yet,
- no production adapter declares capabilities yet,
- no adapter test kit validates capabilities yet.

## Capability rules

Capabilities must be:

- granular enough to prevent false portability,
- conservative by default,
- declared by adapters,
- validated by core when possible,
- tested by the shared adapter test kit once it exists,
- documented when their meaning changes.

An adapter must not claim a capability unless it implements and tests the
behavior. This is especially important for hash behavior, timestamp behavior,
null-safe equality, and semi-structured projections.

Unsupported required capabilities should produce clear diagnostics during
compile or validation when possible. Runtime-only capability failures should be
explicit and should not produce misleading evidence.

## Draft capability names

These names are draft compatibility surfaces. They may change before the
adapter API is stable.

| Capability | Meaning |
| --- | --- |
| `relations` | Adapter can address named relations. |
| `queries` | Adapter can use authored queries as endpoints. |
| `metadata_columns` | Adapter can fetch column metadata. |
| `metadata_precision_scale` | Adapter can report precision and scale metadata where available. |
| `temp_tables` | Adapter can create or use temporary objects. |
| `cte_support` | Adapter can render common table expressions. |
| `row_count` | Adapter can count rows for a relation or query endpoint. |
| `aggregate` | Adapter can compute ungrouped aggregate comparisons. |
| `grouped_aggregate` | Adapter can compute aggregate comparisons segmented by group fields. |
| `key_diff` | Adapter can compare source and target key presence. |
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
- make a capability required for an existing check,
- change diagnostics for unsupported capabilities,
- change which typed operations require a capability.

When a capability changes, update:

- this document,
- `docs/compatibility/typed-check-plan.md` when operation requirements change,
- `docs/compatibility/adapter-api.md` when adapter declarations change,
- adapter test-kit expectations once the test kit exists,
- relevant ADRs when the change is durable.

## Related docs

- `docs/framework/adapters.md`
- `docs/architecture/adapter-interface.md`
- `docs/implementation/adapter-interface-spec.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
