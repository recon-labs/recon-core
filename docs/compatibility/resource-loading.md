# Resource Loading Compatibility

## Purpose

Resource loading affects contract YAML references, package resources, manifest
contents, diagnostics, and future automation that reads project metadata.

The durable design is defined by:

```text
docs/decisions/adr-0017-project-resource-loading-and-precedence.md
```

## Current Status

Current code discovers and parses contract resources only.

Project config already preserves path fields for:

- sample policies,
- tolerance policies,
- schema policies,
- check packs,
- macros.

Those non-contract resource paths are not loaded by current parse or compile
behavior.

## Compatibility Rules

Future resource-loading implementation must preserve these rules:

- unqualified resource references resolve only to local project resources,
- package and framework resources require qualified references,
- `recon_core` is reserved for framework built-ins,
- package namespaces must be unique,
- resource names are unique within resource kind and namespace,
- configurable check-pack resources must follow ADR 0018 config-schema rules,
- macros must not become the primary comparison engine,
- non-contract reference validation may run only for resource kinds loaded by
  the shared resource model.

## Artifact Impact

Adding non-contract resource summaries to `target/manifest.json` is a public
artifact change.

Additive optional manifest fields may keep the current artifact version only
when existing field meanings do not change and readers can ignore unknown
fields safely.

Changing existing manifest file-key semantics, resource type meanings, path
semantics, or checksum semantics requires compatibility review and may require
an artifact version bump.

## Diagnostics

Resource-loading diagnostics must follow ADR 0016 code-family rules and the
rule-specific codes in ADR 0017.

Future changes that add resource-reference validation should update:

- `docs/implementation/errors-and-diagnostics.md`,
- `docs/implementation/testing-plan.md`,
- this compatibility document when external behavior changes.
