# Roadmap

## Roadmap principles

Recon should grow from a small trustworthy core into an ecosystem.

The roadmap should prioritize:

- correctness over breadth,
- explicit validation over convenience magic,
- useful evidence over dashboard polish,
- adapter interface stability before many adapters,
- package standards after core primitives exist.

Milestones, sub-milestones, roadmap items, and epics follow
`docs/planning/milestone-process.md` before implementation. That process defines
the required lightweight prework, high-risk conformance matrix upgrade, and
decimal milestone split rules.

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

MVP run results and evidence should reserve enough scope metadata to avoid
assuming that every future invocation is whole-project. Selector execution is
not part of the 0.1 release line.

Contract capabilities:

- relation-based source/target,
- one contract per file,
- simple `contracts:` multi-contract files,
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

- file-level defaults,
- reusable endpoints,
- query-based source/target,
- tolerance policy files,
- schema policy files,
- improved compiled SQL artifacts,
- basic HTML report,
- `recon list` for manifest-backed resource discovery,
- `recon clean` for safely removing generated artifacts,
- artifact freshness and cleanup for generated outputs,
- minimal contract/path selectors for compile, SQL rendering, and run,
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

Explicit source-target column mapping should also be handled as a separate
post-MVP milestone after adapter metadata, resolved column artifacts, schema
policy behavior, run results, and evidence visibility are stable. Until then,
projects should use canonical compare views or queries rather than relying on
Recon to infer renamed columns.

Sampling:

- deterministic sampling execution design,
- safe numeric modulo or proven portable hash execution only after the Post-MVP
  Milestone 24 sampling gate is resolved,
- incremental-window and persisted sample-key design only; stateful execution
  belongs to Version 0.3 / Post-MVP Milestone 25.

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
- richer result table design, with production table writes gated by Post-MVP
  Milestone 25.5 and adapter write/sink conformance in Post-MVP Milestone 29,
- richer evidence reports,
- split `recon debug` surfaces for profile, connection, contract, and run/check
  diagnostics, with any local secure debug artifact gated separately from
  default terminal/log output,
- orchestrator-friendly CLI behavior,
- typed check-plan model stabilization,
- adapter API versioning,
- adapter interface stabilization,
- adapter compliance tests, including native SQL optimization and dialect
  validation conformance for production execution claims.

Adapters:

- stable typed check-plan model,
- stable adapter interface and API versioning,
- first official SQL adapters prepared for split,
- adapter test kit planning and conformance design,
- `recon-duckdb` extraction deferred until the adapter package/test-kit gates
  are satisfied,
- official external adapter repositories deferred until Post-MVP Milestone 29,
  the adapter test-kit and package split milestone that proves cross-repo
  compatibility,
- experimental adapters allowed only when they do not claim stable execution,
  sink, result-table, or probabilistic-summary compatibility.

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
- richer selectors, including named selectors and check-level selection,
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
- multiple official adapters after shared adapter conformance proves the
  supported execution and sink surfaces,
- package support,
- strong documentation,
- reliable test suite.

## Later opportunities

Possible later capabilities:

- `recon build` as a convenience wrapper after parse, compile, and run behavior stabilizes,
- retry/resume commands after state and run result semantics stabilize,
- Recon Hub,
- GitHub Action,
- orchestrator provider/operator,
- workflow orchestrator integration,
- transformation framework integration patterns,
- data catalog integrations,
- issue/ticket integrations,
- evidence vault,
- approval/sign-off workflows,
- probabilistic key-diff adapter support after Gate 4K and shared adapter
  test-kit conformance in Post-MVP Milestone 29,
- hosted service,
- enterprise policy controls.

Future milestone anchors:

| Milestone | Capability anchor | Public roadmap intent |
| --- | --- | --- |
| M10.7 | User-facing agent onboarding pack and installer | Provide one canonical Recon agent instruction pack for users' own projects, with generated wrappers and safe install/update behavior. |
| M12.5 | Metadata discovery, data profiling, contract suggestions, and relation scope selection | Add scoped metadata inspection, bounded profiling, and advisory suggestions without accepting inferred contracts automatically. |
| M25.6 | Historical profiles, drift, and statistical baseline checks | Add explicit history-backed baseline and drift checks without silent adaptive tolerance mutation. |
| M25.7 | Quality rollups, ownership, and SLA scorecards | Add transparent scorecards that remain drillable to detailed results and evidence. |
| M32.1 | Lineage and observability event export | Export safe Recon metadata to external event, lineage, observability, catalog, or orchestration systems. |
| M32.2 | Optional local Recon MCP server and agent tool interface | Expose a local, safe-by-default tool interface around stable Recon APIs. |
| M32.5 | Workflow actions and remediation integrations | Add approval-first webhooks, tickets, notifications, and remediation hooks after result/evidence boundaries are stable. |
| M42 | Semantic and AI-assisted comparison packages | Add optional non-default semantic or model-assisted comparison packages without presenting similarity as exact reconciliation. |
| M42.5 | Optional Recon AI assistant package | Add an optional bring-your-own-model advisory assistant outside `recon-core` default behavior. |

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
