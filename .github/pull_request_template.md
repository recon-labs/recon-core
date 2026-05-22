# Pull request

## Summary

Describe what changed and why.

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Refactor
- [ ] Tests
- [ ] CI / tooling
- [ ] Design / ADR

## Area

- [ ] Contracts
- [ ] Parser / manifest
- [ ] Compiler
- [ ] Validation
- [ ] Checks
- [ ] Check packs
- [ ] Sampling
- [ ] Tolerances / normalization
- [ ] Schema policies
- [ ] CDC behavior
- [ ] Evidence / artifacts
- [ ] CLI
- [ ] Adapters
- [ ] Packages
- [ ] Documentation

## Tests

Describe tests added or updated.

```text
paste relevant test command output here
```

## Documentation

- [ ] Documentation updated
- [ ] Documentation not needed

Updated docs:

```text
list docs here
```

## Public change impact

- [ ] No public behavior or public contract impact
- [ ] Public behavior changed
- [ ] Contract YAML syntax or validation behavior changed
- [ ] CLI behavior changed
- [ ] Generated artifact format, path, or version changed
- [ ] Adapter interface, capability, typed check plan, or package semantics changed
- [ ] Result model, evidence output, sampling state, or watermark behavior changed

If any public impact is checked:

- [ ] `CHANGELOG.md` updated under `Unreleased`
- [ ] Migration or deprecation guidance added when users must change projects, contracts, CLI usage, artifact consumers, adapters, packages, or evidence workflows
- [ ] ADR added or updated when durable framework behavior changed
- [ ] Not applicable; explained in Notes for reviewers

## Safety checklist

- [ ] No credentials, tokens, private keys, or secrets are included.
- [ ] No customer data or production evidence is included.
- [ ] Generated artifacts under `target/`, `reports/`, or `state/` are not included.
- [ ] Public behavior changes are documented.
- [ ] Changelog, migration, and ADR impact has been handled or explicitly marked not applicable.
- [ ] Durable design changes are captured in `docs/decisions/` when needed.
- [ ] Validation behavior remains strict and does not create misleading evidence.

## Notes for reviewers

Add any risks, open questions, or follow-up work.
