# Resource Loading Compatibility

## Purpose

Resource loading affects contract YAML references, package resources, manifest
contents, diagnostics, and future automation that reads project metadata.

The durable design is defined by:

```text
docs/decisions/adr-0017-project-resource-loading-and-precedence.md
```

## Current Status

Current code discovers local resource source files and parses contract resources
only.

Project config already preserves path fields for:

- sample policies,
- tolerance policies,
- schema policies,
- check packs,
- macros.

Those non-contract resource paths are loaded for file-level indexing only.
Current parse behavior discovers local check-pack, sampling-policy,
tolerance-policy, schema-policy, and macro files, adds them to the
parsed-project file list, and exposes them in `target/manifest.json.files`. It
does not parse those files into named resources, validate references to them,
render macros, execute macros, or add endpoint/package resource behavior.

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

Macro compatibility is staged:

- macro discovery may record source-file metadata and checksums only,
- macro reference validation requires a separate macro-semantics decision,
- macro rendering or execution requires an adapter/rendering compatibility
  review,
- package macro loading requires package namespace, schema, and compatibility
  rules before implementation.

## Artifact Impact

Adding non-contract resource summaries to `target/manifest.json` is a public
artifact change.

Adding local non-contract source-file records to the existing manifest `files`
map is additive when:

- existing `files` keys remain local relative paths,
- existing file fields keep the same names and meanings,
- checksums keep the same byte-content meaning,
- no top-level parsed resource summaries are added.

Under those constraints, `artifact_version: 1` may remain valid. Manifest
readers must not assume every file entry is a contract.

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
