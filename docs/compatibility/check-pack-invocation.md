# Check-Pack Invocation Compatibility

## Purpose

Check-pack invocation is a public contract surface because it controls which
checks are generated and how generated checks inherit severity, sampling,
tolerance, and pack-specific parameters.

## Current Status

Current compiler support is intentionally narrow:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
    - name: recon_core.basic_equivalence
```

Invocation fields other than `name` are rejected by the current compiler.

ADR 0018 locks the future public shape for `config` and `on_empty`, but that
support is not implemented yet.

## Compatibility Rules

When check-pack config support is implemented:

- unknown invocation fields are errors,
- unknown config keys are errors,
- package check packs must declare config schemas before accepting config,
- config that cannot apply to generated checks is an error,
- `on_empty` must be visible in compiled artifacts,
- non-error empty expansion must not hide that no checks were generated,
- config must not disable required safety checks unless a later ADR explicitly
  allows that behavior.

## Artifact Impact

Compiled artifacts must expose check-pack invocation summaries before
`config`, `on_empty: warn`, or `on_empty: skip` are accepted.

The summaries must show the referenced check pack, authored config, resolved
config, empty-expansion policy, generated check IDs, and diagnostics attached to
the invocation.

Adding optional invocation summaries may keep the current compiled artifact
version only if existing readers can safely ignore them and existing field
meanings do not change. Changing existing origin, check ID, or compiled check
semantics requires artifact compatibility review and may require an artifact
version bump.

## Related Docs

- `docs/decisions/adr-0018-check-pack-invocation-config.md`
- `docs/framework/check-packs.md`
- `docs/framework/equivalence-contracts.md`
- `docs/implementation/contract-compiler-and-validation.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/compatibility/artifact-versions.md`
