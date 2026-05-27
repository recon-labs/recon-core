# ADR 0005: Strict Validation and No Silent Magic

## Context

Reconciliation tools can create false confidence if they silently skip checks, silently compare all columns, silently coerce types, or silently ignore schema differences.

A misleading pass is worse than a clear failure.

Recon’s output may be used for cutover, CDC reliability, audit evidence, and engineering sign-off.

## Decision

Recon Core should be strict by default.

The framework must avoid:

- silent all-column comparison,
- silent no-op check packs,
- silent type coercion,
- silent business-key guessing,
- silent schema ignores,
- silent CDC assumptions,
- hidden check-pack behavior.

Unsafe or ambiguous behavior should be an error unless the user explicitly opts into a warning or skip mode.

## Reasoning

Recon must be trustworthy. Trust comes from visible assumptions, clear validation, and evidence that states scope.

Strict validation helps users discover problems before they create false evidence.

## Error defaults

Default errors include:

- row-level check without `grain.keys`,
- row-level check with duplicate keys,
- numeric check on a text column,
- metric referencing an undefined column,
- unknown check pack,
- check pack that expands to nothing when inputs are required,
- missing sampling policy,
- random sampling without persisted keys,
- hash sampling that assumes cross-database equality,
- unsupported adapter capability,
- invalid schema ignore configuration,
- ambiguous CDC behavior for CDC checks.

## Warning defaults

Warnings may include:

- defined column not used by any compiled check,
- timestamp comparison without explicit timezone policy in non-strict mode,
- target freshness lag that makes row-level comparison suspicious,
- metadata validation deferred because adapter metadata is unavailable.

## Consequences

Error messages must be clear and actionable.

Compiled artifacts must show resolved behavior.

Evidence must show full versus sampled scope and any ignored schema elements.

Convenience features are allowed only when explicit.

Column and all-column comparison safety is detailed in ADR 0019.
