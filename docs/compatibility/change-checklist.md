# Compatibility Change Checklist

## Purpose

Use this checklist whenever a change touches a public contract surface from
`docs/compatibility/public-contract-inventory.md`.

The goal is to make compatibility impact explicit before implementation and
review. This checklist is a process guide; it is not a CI gate.

## Checklist

### ADR impact

- [ ] Checked whether the change affects a durable decision.
- [ ] Added or updated an ADR when the change affects public syntax, artifact
      formats, adapter interfaces, validation defaults, package semantics,
      evidence behavior, major architecture, or product scope.
- [ ] Linked the ADR from the relevant docs when useful.

### Documentation impact

- [ ] Updated framework docs for public behavior changes.
- [ ] Updated architecture docs for boundary or interface changes.
- [ ] Updated implementation docs for build guidance changes.
- [ ] Updated user-facing docs when CLI, YAML, evidence, or workflow behavior
      changed.
- [ ] Updated `docs/compatibility/public-contract-inventory.md` when a public
      surface was added, removed, renamed, stabilized, or changed.
- [ ] Checked whether diagnostic code, message, redaction, path, resource, or
      hint rendering changed for any public output surface.

### Changelog impact

- [ ] Updated `CHANGELOG.md` under `Unreleased` for user-visible behavior or
      public contract changes.
- [ ] Put bug fixes under `Fixed`, new capabilities under `Added`, and changed
      semantics or defaults under `Changed`.
- [ ] Explicitly explained why no changelog entry is needed when the touched
      area is public-risk but the change is internal only.

### Migration impact

- [ ] Checked whether users, adapter authors, package authors, CI workflows, or
      artifact readers must change anything.
- [ ] Added migration or deprecation guidance when behavior is breaking or
      requires project changes.
- [ ] Updated compatibility docs and release notes when support ranges changed.

### Test-kit impact

- [ ] Checked whether future or existing adapter test-kit expectations are
      affected.
- [ ] Updated adapter test-kit docs or expectations when adapter API,
      capability, typed operation, SQL rendering, metadata, or execution
      behavior changed.
- [ ] Updated adapter diagnostic expectations when diagnostic messages,
      redaction behavior, or adapter-provided diagnostic fields changed.
- [ ] Documented unsupported capability behavior when adapters are not required
      to implement a new operation.

### Compatibility matrix impact

- [ ] Updated `docs/compatibility/compatibility-matrix.md` when version support,
      artifact versions, typed plan support, adapter API support, capability
      support, package support, or integration status changed.
- [ ] Added a new compatibility dimension when the change introduced one.

### Version constant impact

- [ ] Added or updated a code version constant only when code can produce,
      consume, validate, or reject that versioned surface.
- [ ] Avoided placeholder constants for surfaces that are only planned.
- [ ] Updated `docs/compatibility/artifact-versions.md` when artifact version
      constants changed.

## Review note

If a checklist item is not applicable, say why in the pull request notes. The
expected outcome is explicit reasoning, not unnecessary documentation churn.
