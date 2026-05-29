# Column and Value Comparison Compatibility

## Purpose

Column and value comparison behavior is a public contract surface because it
controls which source and target values are compared, which columns are
eligible for generated checks, and how compiled artifacts explain comparison
scope.

## Current Status

Current implementation preserves authored `columns` as raw data in compiled
contract artifacts and validates the supported authored column declaration
surface during compile. It validates supported column categories and fields,
duplicate declared column names, metric references against an explicit declared
surface, and `sum` metric compatibility with declared `numeric` columns.
Column `timezone` remains reserved and unsupported until timestamp policy
validation is implemented.

It does not implement resolved column metadata in compiled artifacts,
all-column expansion, row-level value checks, column-level check eligibility
enforcement, or adapter metadata column/type validation.

ADR 0019 locks the future column/value comparison surface.

## Compatibility Rules

Future column/value implementation must preserve these rules:

- columns define eligible comparison fields and rules, not actions,
- metrics and checks create execution intent,
- explicit metric/check columns may be used without a contract `columns` block,
- once a contract declares a `columns` block, that block is the explicit
  comparison surface,
- wildcard selectors such as `columns: "*"` must resolve to concrete column
  names before execution,
- all-column expansion must not silently compare only source-target
  intersections,
- source-target column mapping must be explicit and visible if it is ever
  supported,
- invalid check/column type combinations fail validation,
- row-level value checks require key-safety checks and adapter support before
  execution.

## Artifact Impact

Compiled artifacts currently include raw authored `columns`.

Before value checks, all-column expansion, or column/type validation are treated
as implemented, compiled artifacts must expose resolved column metadata:

- declared categories,
- canonical column names,
- all-column requests,
- resolved concrete column lists,
- excluded identity columns,
- explicitly ignored columns,
- adapter metadata validation status,
- per-check required columns,
- deferred validation diagnostics.

Typed check plans must contain concrete column names only. They must not contain
raw wildcard selectors.

Adding optional resolved-column fields may keep the current compiled artifact
version only if existing readers can safely ignore them and existing field
meanings do not change. Changing existing `columns` field meaning, stable check
IDs, required-column semantics, or typed operation payloads requires
compatibility review and may require an artifact version bump.

## Related Docs

- `docs/decisions/adr-0019-column-and-value-comparison-surface.md`
- `docs/framework/equivalence-contracts.md`
- `docs/framework/checks.md`
- `docs/implementation/contract-compiler-and-validation.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/compatibility/artifact-versions.md`
