# Release Plan

## Release philosophy

Recon should release small, trustworthy versions.

Each release should have:

- clear scope,
- working examples,
- passing tests,
- updated docs,
- visible artifact behavior,
- no hidden behavior that contradicts the documented contract model.

## Versioning

Recon should use semantic versioning once the public package is released.

Before 1.0, breaking changes are allowed but should be documented clearly.

Development branches may keep the package version at `0.0.0` until the project
is intentionally prepared for a public release.

Expected format:

```text
0.1.0
0.2.0
0.3.0
1.0.0
```

## Milestone and release mapping

Milestones 1-10 are the MVP build sequence.

Completing Milestone 10 does not automatically release the package. It means the
project is eligible for a 0.1 release-readiness pass.

The 0.1 release line starts only after:

- Milestones 1-10 are complete,
- the MVP acceptance criteria pass,
- the release readiness checklist passes,
- docs and examples match real behavior,
- the user explicitly approves a version bump, tag, or publish step.

Post-MVP roadmap work belongs to the 0.2 line after the 0.1 release decision.
Agents should not infer a release, tag, publish, or version bump without an
explicit user request.

## Release readiness checklist

Before each release:

- tests pass,
- examples run,
- docs reflect implementation behavior,
- CLI help is accurate,
- artifact paths are stable for that release,
- migration notes are written if config behavior changed,
- known limitations are documented,
- package metadata is correct,
- license and contribution docs are present.

## 0.1 release

Release purpose:

> Demonstrate the core Reconciliation as Code workflow.

This is the MVP release line.

Included:

- CLI skeleton,
- parse/compile/run commands,
- project config,
- relation-based contracts,
- basic contract validation,
- basic check packs,
- basic aggregate metric checks,
- simple multi-contract files,
- manifest artifact,
- compiled checks artifact,
- run results artifact,
- simple examples.

Release quality bar:

- a new user can run one local example from docs,
- errors are understandable,
- compiled artifacts show what will run,
- results show what passed or failed.

## 0.2 release

Release purpose:

> Make the framework practical for early real projects.

Included:

- query-based contracts,
- defaults,
- endpoint refs,
- tolerance policy files,
- schema policy files,
- richer aggregate checks,
- basic value checks,
- basic HTML evidence,
- early CDC check pack behavior.

Release quality bar:

- a user can model a realistic migration/refactor comparison,
- source/target surrogate-key differences can be handled with views or queries,
- schema ignores and null policies are explicit,
- check-pack expansion is inspectable.

## 0.3 release

Release purpose:

> Make recurring validation and adapter development realistic.

Included:

- state/watermark behavior,
- incremental windows,
- previous failure retest,
- persisted sample keys,
- typed check-plan model stabilization,
- adapter API versioning,
- adapter interface stabilization,
- adapter compliance tests,
- production-oriented result tables or clear design.

Release quality bar:

- a user can schedule recurring checks,
- watermarks behave predictably,
- adapter authors have a clear API version and test kit path.

## 1.0 release

Release purpose:

> Stabilize the public framework contract.

Required:

- stable contract schema,
- stable CLI,
- stable artifact formats,
- stable adapter interface,
- stable check result model,
- strong documentation,
- official examples,
- at least two credible adapters,
- clear package ecosystem direction.

## Distribution

Initial distribution should be through Python packaging.

Expected install:

```bash
pip install recon-core
```

Current local development extra:

```bash
pip install "recon-core[duckdb]"
```

Long-term adapter packages:

```bash
pip install recon-postgres recon-snowflake
```

## Pre-release channels

Potential pre-release labels:

```text
0.1.0a1
0.1.0b1
0.1.0rc1
```

Use pre-releases when artifact formats or contract schema are likely to change.

## Deprecation policy

Before 1.0, breaking changes can happen but should be documented.

After 1.0:

- deprecate before removing,
- warn clearly,
- document migration paths,
- keep artifacts stable when possible.

## Documentation release requirements

Every release should update:

- README,
- quickstart,
- CLI docs,
- contract docs,
- examples,
- known limitations,
- changelog.

## Release principle

Do not release features that make reconciliation look successful when assumptions are unsafe.

Strict errors are better than misleading evidence.
