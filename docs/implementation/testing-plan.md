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

- check packs expand,
- metrics compile into checks,
- columns do not create checks,
- empty check pack errors,
- sampling resolves per check,
- tolerances resolve by precedence,
- schema policies apply,
- CDC config validates.

### Validation tests

Each locked validation rule should have tests.

Rules include:

- no silent all-column comparison,
- row-level checks require keys,
- duplicate keys block row-level checks,
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

- capability declarations,
- metadata shape,
- relation existence,
- query execution,
- quoting,
- limit compilation.

Production adapters should eventually use an adapter test kit.

### Artifact tests

Tests for generated artifacts.

Examples:

- manifest JSON shape,
- compiled contract shape,
- compiled checks shape,
- run results shape,
- diagnostics included,
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
