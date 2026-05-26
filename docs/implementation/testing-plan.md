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

Column and value-comparison tests should follow ADR 0019. Before accepting
typed column validation, all-column expansion, or row-level value checks, tests
should cover duplicate declarations, unknown categories, undeclared references,
invalid selectors, check/category incompatibility, unused declared columns,
metadata-deferred validation, and resolved column artifact visibility.

Tolerance, null, and normalization tests should follow ADR 0009. Before
accepting policy resolution or execution, tests should cover numeric shorthand
and object equivalence, invalid tolerance shapes, unsupported relative or
timestamp tolerance in the current milestone, invalid null policy values,
invalid normalization operations, type incompatibility, precedence, and
resolved policy artifact visibility.

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
