# Package Layout

## Python package shape

Recommended initial source layout:

```text
src/
  recon_core/
    __init__.py
    cli/
    project/
    config/
    resources/
    parser/
    compiler/
    planner/
    checks/
    adapters/
    execution/
    artifacts/
    evidence/
    state/
    diagnostics/
    utils/
```

## `cli/`

Command-line entry points.

Expected modules:

```text
cli/
  main.py
  commands/
    init.py
    parse.py
    compile.py
    run.py
```

CLI modules should orchestrate application services but avoid framework logic.

## `project/`

Project discovery and root resolution.

Responsibilities:

- find `recon_project.yml`,
- resolve project root,
- resolve configured paths,
- handle generated artifact paths.

## `config/`

Project configuration models.

Responsibilities:

- `recon_project.yml`,
- profiles configuration shape,
- package configuration shape,
- selectors configuration shape.

## `resources/`

Typed resource models.

Possible resources:

- contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoint definitions,
- macros.

## `parser/`

File parsing and structural validation.

Responsibilities:

- load YAML,
- validate schema shape,
- build parsed resources,
- create manifest inputs.

## `compiler/`

Compilation from parsed resources to compiled contracts/checks.

Responsibilities:

- resolve defaults,
- resolve refs,
- expand check packs,
- compile metrics,
- resolve sampling,
- resolve tolerances,
- resolve schema policies,
- resolve CDC policies,
- generate compiled artifacts.

## `planner/`

Turns compiled checks into executable plans.

Responsibilities:

- order checks,
- group checks when possible,
- determine adapter needs,
- prepare SQL/check jobs.

## `checks/`

Check definitions and built-in check pack logic.

Expected structure:

```text
checks/
  base.py
  registry.py
  builtins/
    coverage.py
    aggregate.py
    value.py
    schema.py
    cdc.py
```

## `adapters/`

Base adapter interface and lightweight development adapters.

Production adapters should eventually live in separate packages.

Expected structure:

```text
adapters/
  base.py
  capabilities.py
  metadata.py
  types.py
```

## `execution/`

Runtime execution.

Responsibilities:

- adapter dispatch,
- query execution,
- check result collection,
- run lifecycle.

## `artifacts/`

Read/write generated artifacts.

Responsibilities:

- manifest writer,
- compiled contract writer,
- compiled check writer,
- run result writer,
- compiled SQL writer.

## `evidence/`

Human-facing and machine-facing evidence.

Responsibilities:

- failure detail writer,
- report generation,
- evidence references,
- redaction hooks later.

## `state/`

State backends.

Initial state may be file-based.

Future state may include database-backed watermarks, sample keys, and previous failures.

## `diagnostics/`

Errors, warnings, validation messages, and user-facing diagnostics.

Diagnostics should be structured so CLI output, JSON artifacts, and reports can all reuse them.

## `utils/`

Small utilities only.

Avoid putting framework logic in `utils/`.

## Import rule

Domain models and interfaces should not import CLI modules.

Adapters should depend on core interfaces, not the other way around.
