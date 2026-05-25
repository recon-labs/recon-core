# ADR 0006: Contract Compiler and Validation Rules

## Context

Recon contracts can contain high-level declarations and reusable resources.

Examples:

- check packs,
- metrics,
- sampling policies,
- tolerance policies,
- schema policies,
- CDC policies,
- defaults,
- refs.

Before running checks, Recon must resolve these into an explicit plan and validate that plan.

## Decision

Recon Core should use a compiler and validator pipeline.

The compiler turns authored contracts into explicit compiled checks.

The validator rejects unsafe, ambiguous, incompatible, or underspecified behavior before execution whenever possible.

## Compiler responsibilities

The compiler should:

- load contracts,
- resolve defaults,
- resolve refs,
- expand check packs,
- compile metrics into checks,
- resolve sampling for each check,
- resolve tolerance and null policy precedence,
- apply schema policy rules,
- apply CDC policy rules,
- attach evidence settings,
- produce human-readable compiled artifacts.

## Validator responsibilities

The validator should check:

- contract names are unique,
- source and target are valid,
- exactly one of `relation` or `query` is used per endpoint,
- row-level checks have keys,
- row-level checks validate key uniqueness,
- columns exist where metadata is available,
- check types are compatible with column types,
- metrics reference valid columns,
- sample policies exist,
- tolerance syntax is valid,
- schema ignores are explicit,
- CDC configuration is sufficient,
- adapter capabilities support requested checks.

## Validation timing

Some validation can happen during parse.

Some validation requires compile.

Some validation requires adapter metadata and may occur before run or during run.

If validation must be deferred, the compiled plan should say so.

## Generated artifacts

The compiler should write:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
```

Compiled checks should show:

- check name,
- check type,
- source and target,
- keys,
- columns,
- metrics,
- sampling,
- tolerances,
- null rules,
- schema ignores,
- CDC mode,
- evidence settings,
- severity.

## Consequences

The implementation should keep parser, compiler, validator, and runner responsibilities separate.

Tests should cover both valid and invalid contracts.

Future coding agents should update this decision or create a new one when compiler behavior changes.

ADR 0019 extends these compiler validation rules for column declarations,
column references, all-column expansion, and value-check compatibility.
