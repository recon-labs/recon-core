# Roadmap

## Roadmap principles

Recon should grow from a small trustworthy core into an ecosystem.

The roadmap should prioritize:

- correctness over breadth,
- explicit validation over convenience magic,
- useful evidence over dashboard polish,
- adapter interface stability before many adapters,
- package standards after core primitives exist.

## Version 0.1

Primary goal:

> Prove the Reconciliation as Code workflow end to end.

Version 0.1 is the MVP release line. It should be considered release-ready only
after Milestones 1-10 are complete and the MVP acceptance criteria pass. Until a
release decision is made, development branches may keep the package version at
`0.0.0`.

Core capabilities:

- CLI foundation,
- core commands: `recon init`, `recon parse`, `recon compile`, and `recon run`,
- project loading,
- contract parsing,
- basic validation,
- manifest generation,
- contract compilation,
- compiled checks,
- basic run results,
- terminal summary,
- basic evidence artifacts.

Contract capabilities:

- relation-based source/target,
- one contract per file,
- explicit columns,
- explicit metrics,
- `grain.keys`,
- basic sampling config,
- numeric tolerance config.

Checks:

- row count,
- missing keys,
- extra keys,
- null source keys,
- null target keys,
- duplicate source keys,
- duplicate target keys,
- sum metric diff.

Built-in check packs:

- `recon_core.basic_equivalence`.

Explicit metrics are the first aggregate path. `recon_core.aggregate_equivalence`
is deferred until its inference behavior is explicitly designed.

Artifacts:

- `target/manifest.json`,
- `target/compiled_contracts/`,
- `target/compiled_checks/`,
- `target/run_results.json`,
- optional `target/compiled_sql/`,
- optional basic HTML report.

## Version 0.2

Primary goal:

> Make Recon useful for repeated project work and early CDC validation.

Version 0.2 is post-MVP roadmap work. It starts after the 0.1 release decision,
not merely after an arbitrary milestone branch.

Capabilities:

- multiple contracts per file,
- file-level defaults,
- reusable endpoints,
- query-based source/target,
- tolerance policy files,
- schema policy files,
- improved compiled SQL artifacts,
- basic HTML report,
- `recon list` for manifest-backed resource discovery,
- `recon clean` for safely removing generated artifacts,
- selector design for tag/name selection,
- improved error and warning model.

Checks:

- exact value match,
- numeric tolerance row-level match,
- timestamp tolerance match,
- explicit `min`, `max`, `avg`, and `count_distinct` metric diffs,
- grouped aggregate diff,
- column presence,
- type compatibility,
- precision/scale compatibility.

Aggregate metric expansion should be handled as an explicit post-MVP milestone.
`recon_core.aggregate_equivalence` should remain gated until its expansion and
inference behavior is designed and documented.

Sampling:

- deterministic hash or safe numeric modulo,
- incremental window,
- persisted sample keys design.

CDC:

- first `recon_core.cdc_equivalence` implementation,
- freshness lag,
- latest window count,
- incremental key coverage,
- explicit `cdc.keys`,
- explicit delete-mode config.

## Version 0.3

Primary goal:

> Make Recon production-schedulable and adapter-extensible.

Capabilities:

- state backend design,
- watermarks,
- previous failure retest,
- persisted random samples,
- richer result tables,
- richer evidence reports,
- `recon debug` for project, profile, adapter, and connection diagnostics,
- Airflow-friendly CLI behavior,
- typed check-plan model stabilization,
- adapter API versioning,
- adapter interface stabilization,
- adapter compliance tests.

Adapters:

- stable typed check-plan model,
- stable adapter interface and API versioning,
- first official SQL adapters split or prepared for split,
- adapter test kit planning.

Checks:

- update propagation,
- delete propagation,
- operation count diff,
- null/empty-string normalization,
- string normalization.

## Version 0.4

Primary goal:

> Make Recon package-friendly and team-scalable.

Capabilities:

- package resource loading,
- `packages.yml`,
- early `recon deps`,
- local check pack packages,
- sample/tolerance/schema policy packages,
- richer selectors,
- documentation generation command.

Ecosystem:

- official CDC package,
- official migration package,
- official sampling policies,
- official tolerance policies.

## Version 1.0

Primary goal:

> Provide a stable open-source framework API and project model.

Expected stability:

- contract schema,
- CLI commands,
- artifact formats,
- adapter interface,
- check result model,
- package model,
- validation rules.

Expected capabilities:

- production-ready CLI,
- stable evidence artifacts,
- stable parse/compile/run flow,
- multiple official adapters,
- package support,
- strong documentation,
- reliable test suite.

## Later opportunities

Possible later capabilities:

- `recon build` as a convenience wrapper after parse, compile, and run behavior stabilizes,
- retry/resume commands after state and run result semantics stabilize,
- Recon Hub,
- GitHub Action,
- Airflow provider/operator,
- Dagster integration,
- dbt integration patterns,
- data catalog integrations,
- issue/ticket integrations,
- evidence vault,
- approval/sign-off workflows,
- hosted service,
- enterprise policy controls.

## Things to avoid

Avoid building too early:

- broad UI,
- complex package registry,
- too many adapters before the interface is stable,
- auto-mapping inference,
- fuzzy matching,
- generic data quality sprawl,
- cloud product before open-source core is credible.

## Roadmap decision rule

A feature belongs earlier when it strengthens the core loop:

```text
contract -> compile -> run -> evidence
```

A feature belongs later when it depends on ecosystem maturity, many users, or stable extension APIs.
