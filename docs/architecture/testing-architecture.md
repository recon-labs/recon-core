# Testing Architecture

## Testing goals

Recon should be tested around framework behavior, not only code coverage.

Tests should protect:

- public YAML behavior,
- validation rules,
- compiler expansion,
- artifact formats,
- check results,
- adapter interfaces,
- evidence generation.

## Test categories

### Unit tests

Fast tests for small functions and models.

Examples:

- config parsing,
- tolerance precedence,
- sampling resolution,
- schema ignore matching,
- diagnostic formatting.

### Parser tests

Tests for YAML loading and structural validation.

Examples:

- valid contract parses,
- missing required fields fail,
- duplicate contract names fail,
- invalid resource shape fails.

### Compiler tests

Tests for resolved behavior.

Examples:

- check packs expand,
- check-pack invocation config follows ADR 0018 before it is accepted,
- column and value-comparison behavior follows ADR 0019 before it is accepted,
- tolerance, null, and normalization behavior follows ADR 0009 before it is
  accepted,
- metrics compile into checks,
- empty expansion errors,
- sampling override wins,
- tolerance precedence works,
- schema policy applies,
- CDC config validates.
- typed check plans are produced with expected operation requirements.
- key identity and check requirement metadata is compiled.

### Check engine tests

Tests for check execution behavior using fake or local adapters.

Examples:

- row count pass/fail,
- duplicate keys block row diff,
- null keys block row diff,
- null keys block row diff,
- CDC propagation checks require CDC keys,
- aggregate sum diff,
- value mismatch evidence,
- schema ignore behavior.

### Artifact tests

Tests for generated artifacts.

Examples:

- manifest shape,
- compiled check shape,
- run result shape,
- blocked checks include prerequisites and skip reasons,
- diagnostic inclusion,
- artifact version field.

### Adapter contract tests

Tests every adapter should pass.

Examples:

- relation exists,
- metadata columns,
- quoting,
- limit compilation,
- typed operation rendering,
- adapter API version compatibility,
- timestamp behavior,
- capability declarations.

Shared adapter tests should fail when core adds a required typed operation and
an adapter has not implemented rendering or declared the capability unsupported.

## Test data

Use small deterministic fixtures.

Do not use real customer data.

Prefer local/dev databases or in-memory fixtures for core tests.

## Golden files

Golden artifact tests can be useful for compiled outputs.

Golden files should be stable and easy to review.

Do not overuse golden files for volatile output.

## TDD expectations

Use test-driven development for non-trivial behavior.

Validation rules should have explicit tests for both valid and invalid cases.
Validation tests should assert diagnostic code, severity, and phase ownership
according to
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

## CI expectations

CI should run:

```text
unit tests
parser tests
compiler tests
artifact tests
linting
format checks
type checks
```

Adapter integration tests may run separately when external systems are required.

Production adapter repositories should run a shared adapter test kit in CI once
the adapter API stabilizes.

## Design principle

Tests should prevent Recon from producing misleading evidence.
