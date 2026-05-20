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

Expected format:

```text
0.1.0
0.2.0
0.3.0
1.0.0
```

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

Included:

- CLI skeleton,
- parse/compile/run commands,
- project config,
- relation-based contracts,
- basic contract validation,
- basic check packs,
- basic aggregate metric checks,
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
- multiple contracts per file,
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

Possible future extras:

```bash
pip install "recon-core[postgres]"
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
