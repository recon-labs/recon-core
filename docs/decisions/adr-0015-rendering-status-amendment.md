# ADR 0015 Amendment: Rendering Status Migration

## Context

ADR 0015 defines compiled artifact schema and rendering metadata for compiled checks. ADR 0020 later locks the Milestone 6 adapter-aware SQL rendering boundary and rendering-status migration target.

## Amendment

For current pre-Milestone-6 compiled artifacts, compiler models may still expose draft rendering statuses from the original implementation.

Milestone 6 adapter-aware rendering should migrate rendering status values to:

```text
not_rendered
rendered
blocked
failed
```

Meanings:

- `not_rendered`: adapter-aware rendering was not requested or no renderer was available.
- `rendered`: all SQL needed for the check was rendered.
- `blocked`: rendering was intentionally skipped because validation failed.
- `failed`: rendering was attempted but failed because of an adapter or rendering error.

The migration from earlier draft statuses to `blocked` and `failed` must update code, tests, compiled-artifact examples, and compatibility docs together.

## Relationship to ADR 0015

This amendment qualifies ADR 0015's rendering-status section. ADR 0015 remains the compiled artifact schema decision, but ADR 0020 and this amendment control Milestone 6 adapter-aware rendering-status migration wording.
