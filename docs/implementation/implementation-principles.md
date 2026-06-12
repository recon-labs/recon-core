# Implementation Principles

## Build the framework, not a script collection

Recon Core should be implemented as a framework with stable layers.

Avoid mixing:

- CLI rendering,
- parsing,
- validation,
- compilation,
- SQL generation,
- execution,
- evidence writing.

Each subsystem should have clear inputs and outputs.

## Prefer explicit models

Use typed models for user-authored resources, parsed resources, compiled resources, execution plans, and results.

Avoid passing raw dictionaries deep into the engine.

Raw YAML should be converted into typed models near the parser boundary.

## Validate early and clearly

Invalid contracts should fail before execution when possible.

Examples:

- unknown check pack,
- duplicate contract name,
- row-level check without keys,
- metric referencing a missing column,
- numeric check on a text column,
- random sampling without persisted keys,
- unsupported adapter capability.

## Compile before execution

The runner should execute compiled checks, not raw authored YAML.

Compilation should resolve:

- defaults,
- refs,
- check packs,
- metrics,
- sampling,
- tolerances,
- null rules,
- schema policies,
- CDC settings,
- evidence settings.

## Generated behavior must be inspectable

If Recon infers, expands, or resolves behavior, it should appear in generated artifacts.

Important artifacts:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/ when adapter SQL rendering is requested and succeeds
target/run_results.json
```

## Keep adapters isolated

Core should depend on adapter interfaces, not production database drivers.

Production adapters should eventually live outside `recon-core`.

Core may contain local/dev adapters for tests and examples.

Core owns comparison semantics and typed check plans.

Adapters own metadata access, capability declarations, dialect SQL rendering,
and execution.

Do not hide reconciliation behavior inside adapter-specific SQL or macro logic.
Do not bypass typed plans with direct authored YAML-to-SQL compilation, untyped
`select *` comparison plans, or syntax-only adapter compatibility claims.

## Make errors actionable

Every error should tell the user:

- what failed,
- where it failed,
- why it failed,
- how to fix it when possible.

## Test behavior, not only functions

Tests should assert framework behavior:

- authored YAML becomes expected compiled checks,
- invalid contracts produce expected diagnostics,
- check results produce expected artifacts,
- unsafe assumptions are blocked.

## Avoid convenience that weakens trust

Do not add convenience behavior that can make Recon produce misleading evidence.

Strict errors are better than quiet success.
