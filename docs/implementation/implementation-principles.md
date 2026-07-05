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

## Avoid Recon anti-patterns

A bug fix, code-review fix, or feature change should preserve the owner boundary
of the behavior it touches. The right fix is the smallest design-conformant
change, not the shortest patch that makes a local assertion pass.

Treat these patterns as fix triggers:

- scattered validation: the same contract, policy, or capability rule is checked
  in multiple layers instead of at the owning boundary,
- duplicated policy logic: reconciliation semantics, safety checks, or evidence
  rules are copied instead of shared through the owning model, helper, or
  service,
- exception swallowing: parse, compile, execution, adapter, or artifact failures
  are hidden behind quiet defaults or broad catches,
- boolean blindness: a bare true/false result replaces a typed result,
  diagnostic, reason code, or evidence detail that callers need,
- leaky abstraction: parser, compiler, runner, adapter, CLI, or artifact code
  reaches through another layer instead of using its public model or interface,
- wrong-layer adapter coupling: core behavior depends on concrete database
  drivers, dialect quirks, or adapter internals instead of adapter interfaces
  and typed plans,
- god service or module growth: one service accumulates parsing, validation,
  compilation, execution, and artifact responsibilities without a documented
  boundary,
- hidden fallback: Recon silently substitutes default behavior when the authored
  contract, adapter capability, schema, or evidence request is unsupported,
- weakened tests: assertions are deleted, loosened, or broadened so a change
  passes without still proving the required behavior,
- regression-memory drift: a reusable regression or public-surface requirement
  is fixed in code but not preserved in regression-capture metadata when it
  should carry forward.

If avoiding one of these patterns requires a same-scope refactor inside the
touched boundary, include that refactor with the fix. If the required refactor
crosses public contracts, adapter APIs, generated artifacts, or broad module
ownership, do not hide it inside a local fix; complete the required design or
planning decision before changing behavior.

## Avoid convenience that weakens trust

Do not add convenience behavior that can make Recon produce misleading evidence.

Strict errors are better than quiet success.
