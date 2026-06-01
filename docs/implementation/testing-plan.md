# Testing Plan

## Purpose

This document defines the implementation testing plan for Recon Core.

Tests should protect public behavior and prevent misleading evidence.

## Test layers

### Unit tests

Fast tests for pure functions and small models.

Examples:

- config defaults,
- path resolution,
- name validation,
- tolerance precedence,
- schema ignore matching,
- sampling precedence.

### Parser tests

Tests for authored YAML.

Examples:

- one contract per file,
- multiple contracts per file,
- duplicate contract names,
- missing source/target,
- invalid YAML,
- unknown fields.

Milestone 4.6 resource-indexing tests should cover:

- missing default optional non-contract paths are skipped,
- explicitly configured missing optional paths fail with
  `RC_PARSE_RESOURCE_PATH_NOT_FOUND`,
- catalog entries with `explicit_missing_is_error: false` skip missing authored
  paths,
- non-contract source-file discovery is deterministic,
- overlapping configured paths deduplicate by real path,
- file checksums are stable,
- macro files are indexed only as `macro_file` source files,
- index-only non-contract YAML files are not parsed as named resources,
- endpoint files are not loaded before `endpoint-paths` is implemented.

### Compiler tests

Tests for explicit generated behavior.

Examples:

- stable compiled IDs,
- compiled model serialization,
- check packs expand,
- metrics compile into checks,
- columns do not create checks,
- empty check pack errors,
- sampling resolves per check,
- tolerances resolve by precedence,
- schema policies apply,
- CDC config validates.
- typed check plans include expected operations,
- compiled artifacts reference typed plans and rendered SQL.

### Validation tests

Each locked validation rule should have tests.

Milestone 5 validation tests should assert the diagnostic code, severity, and
phase ownership defined in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.
Future validation expansions for sampling, tolerance, columns, check-pack
config, resource references, adapters, results, or evidence should lock their
rule-specific diagnostics before implementation and test those diagnostics
explicitly.

Check-pack invocation config tests should follow ADR 0018. Before accepting
`config`, `on_empty: warn`, or `on_empty: skip`, tests should cover typed
invocation parsing, schema validation, unknown keys, duplicate invocations,
empty-expansion diagnostics, precedence, and compiled artifact visibility.

Column and value-comparison tests should follow ADR 0019. Current typed column
validation tests should cover duplicate declarations, unknown categories,
undeclared references, invalid selectors, and check/category incompatibility.
Before accepting column-level eligibility, unused-column warnings, all-column
expansion, resolved column metadata, adapter metadata validation, or row-level
value checks, tests should cover those behaviors explicitly.

Tolerance, null, and normalization tests should follow ADR 0009. Before
accepting policy resolution or execution, tests should cover numeric shorthand
and object equivalence, invalid tolerance shapes, unsupported relative or
timestamp tolerance in the current milestone, invalid null policy values,
invalid or duplicate null sentinels, invalid normalization steps, invalid or
unsupported MVP regex, adapter capability blocking for regex-dependent
execution, type incompatibility, precedence, and resolved policy artifact
visibility.

Rules include:

- no silent all-column comparison,
- row-level checks require keys,
- duplicate keys block row-level checks,
- null keys block row-level checks,
- CDC propagation checks require CDC keys,
- `basic_equivalence` without grain fails validation,
- invalid check/column types error,
- random sampling requires persisted keys,
- hash sampling does not assume portability,
- schema ignores are explicit,
- CDC mode is required for CDC checks.

### Check engine tests

Tests for built-in checks.

Examples:

- row count pass/fail,
- missing keys,
- extra keys,
- duplicate source keys,
- duplicate target keys,
- sum diff,
- grouped aggregate diff later.

### Adapter tests

Base adapter tests should cover:

- adapter API version compatibility,
- capability declarations,
- metadata shape,
- relation existence,
- query execution,
- quoting,
- limit compilation,
- typed operation rendering,
- unsupported capability diagnostics.

Adapter tests for key-dependent operations should cover null-key detection,
duplicate-key detection, key-diff rendering, and CDC-key operation rendering
where supported.

Production adapters should eventually use a shared adapter test kit. The same
test kit should run in every adapter repo and should include operation-rendering
golden tests.

The shared adapter test kit should include adapter API conformance tests
separate from SQL comparison conformance. These tests should verify adapter
registry and factory behavior, including that a factory returning neither an
adapter nor diagnostics fails with `RC_ADAPTER_RESOLUTION_FAILED` instead of
allowing adapter-aware rendering or execution to succeed.

Before creating, publishing, or splitting a shared adapter test-kit repository,
define a SQL comparison conformance matrix. The matrix should make comparison
semantics executable across adapters and should cover:

- null-safe equality,
- distinct non-null key-diff semantics,
- nullable grouped aggregate keys,
- no implicit type coercion or combination-casting matches,
- representative cross-type value cases such as numeric/string,
  boolean/numeric/string, decimal/float, and date/timestamp where supported,
- key-diff type mismatches fail instead of returning misleading missing/extra
  key rows,
- grouped aggregate key type mismatches fail with clear Recon or adapter-level
  errors instead of raw dialect binder errors,
- aggregate input column and value type mismatches fail instead of being
  compared through dialect implicit casts,
- boolean aggregate inputs fail for `sum` semantics when an engine treats them
  as true-value counts instead of numeric aggregates,
- empty source/target relations with mismatched key or group-key types still
  fail instead of producing empty trustworthy-looking comparison output,
- grouped aggregate renderers do not use cross-type coalescing for source and
  target group keys,
- capability-specific behavior for unsupported casts, normalization, hashing,
  timestamp, semi-structured, or metadata-dependent comparisons,
- clear diagnostics or unsupported capability results when an adapter cannot
  safely perform a comparison.

### Artifact tests

Tests for generated artifacts.

Examples:

- manifest JSON shape,
- top-level artifact headers,
- compiled contract shape,
- compiled checks shape,
- invocation IDs included for compile and run artifacts,
- run results shape,
- diagnostics included,
- check requirements included,
- identity metadata included,
- blocked checks include `blocked_by` and `skip_reason`,
- artifact versions included.

Manifest tests for resource indexing should assert that non-contract files are
included in `files` with path, `resource_type`, and checksum only, and that no
top-level parsed resource summaries are emitted before those schemas exist.

### CLI tests

Tests for command behavior.

Examples:

- `recon init`,
- `recon parse`,
- `recon compile`,
- `recon run`,
- exit codes,
- terminal summaries.

## Golden tests

Golden files can be used for compiled artifacts.

Use golden tests carefully so they verify public behavior without becoming brittle.

## Test fixtures

Fixtures should be small and deterministic.

Avoid real customer data.

Use fake business examples.

## Continuous integration

CI should run:

```text
format check
lint
type check
unit tests
parser tests
compiler tests
artifact tests
CLI tests
```

Adapter integration tests that require external services can run separately.

## Design principle

If a behavior can affect evidence trust, it needs tests.
