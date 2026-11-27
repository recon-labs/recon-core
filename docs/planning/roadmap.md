# Roadmap

## Current implementation authorization (2026-11-27)

The maintainer explicitly approved the consolidated native-first design,
including its adapter-scoped project/target/connection configuration and
precedence, and separately authorized implementation. This checkpoint
supersedes earlier suspension/approval-pending wording below, not any
required outcome or exit proof. Implement only the approved replacement
on draft PR #42. No merge, release, production activation, or guard removal
before the applicable proof and separate merge approval. Split Decision:
Already Split / Follow Existing Split. No completed milestone reopening.

Approved design revision c1d82f1e55fc0d5160709b8a0fd276e984ad0af8;
base main b001d14de1fb613beaaad1f3e914f81dfb125cac.
CI 45965307969: all ten standard jobs concluded success (three Python test
jobs, three DuckDB semantic jobs, four pinned DuckDB compatibility jobs).
This is design-baseline CI, not proof of the replacement implementation.
Historical candidate baseline 64caf7a0709064cc60e143386c7dfaaaaaa86abe
remains available in history. Existing A1-A13/R1-R10/B8-B10/P1-P6 outcomes,
M8.2/M8.3/M9.5/M10.8/M11-M13/M29 and all future configuration gates retain
their assignments. The mechanism-specific scope reductions below are
approved as part of the replacement, with equivalent applicable outcomes
required before retirement. No gate is closed.

See the [approved M8.1.2 prework](milestone-8-1-2-prework.md) for the exact configuration, candidate/capture disposition and ordered implementation proof.

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

M8.1.2 native-first replacement implemented on draft PR #42, final cumulative validation and separate merge approval pending. See [approved prework](milestone-8-1-2-prework.md). Own hardware-aware adapter-scoped policy, project/target/connection precedence, measured calibration, native interruption/confirmed release and current scratch cleanup prerequisites; no mandatory worker or persistent recovery. Remaining invocation lifecycle and cumulative resources belong to M8.2; safe resource metadata to M8.3. See [mandatory assignments](execution-resource-safety-assignments.md).

Primary goal:

> Prove the Reconciliation as Code workflow end to end.

Version 0.1 is the MVP release line. It should be considered release-ready only
after Milestones 1-10 are complete and the MVP acceptance criteria pass. Until a
release decision is made, development branches may keep the package version at
`0.0.0`.

The runner/results umbrella is delivered through M8.1 scan-budget configuration
and enforcement (including basic execution advisories), M8.2 execution planning
and run lifecycle, and M8.3 run-result publication and CLI finalization. See
[the split assignment](milestone-8-split-assignment.md). Each requires separate
high-risk prework; the split does not admit additional comparison operations.

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

After the 0.1 release-readiness decision, review the ecosystem roadmap's
repository introduction checkpoints alongside core milestone planning. Early
experimental test-kit, PostgreSQL and Snowflake work may proceed in parallel
only after their assigned prework and approvals; no official adapter release
or compatibility promise is implied.

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
- official external adapter releases and stable compatibility claims deferred
  until Post-MVP Milestone 29 and capability-specific cross-repo conformance,
- earlier experimental test-kit and adapter work recommended at the post-MVP
  checkpoints in [the ecosystem roadmap](ecosystem-roadmap.md#repository-introduction-checkpoints),
  subject to existing pre-creation and safety gates, with no stable execution,
  sink, result-table, or probabilistic-summary compatibility claims.

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

## Mandatory M9.5 delivery checkpoint

M9.5 (lossless type compatibility for existing key and aggregate checks) is a mandatory pre-MVP implementation milestone after M8/M9 and the targeted M7.4 correction. M10 exit and 0.1 release readiness require completed M9.5 on main; no mere planning or historical gate closure satisfies it. See the [build order](../implementation/mvp-build-order.md) and [type compatibility assignments](type-compatibility-assignments.md).

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is implemented and verified on main (PR #38). Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.


Gate 4L configuration scope/precedence extension, also Gate 4I/4J/8C:
M8.1.2 owns typed scoped configuration, reset/precedence, separation from
connection identity, selected-only validation, alias conflicts, both execution
modes and regression proof for prior configuration/profile/runtime behavior.
M8.2 owns run-wide cumulative limits/concurrency and lifecycle; M8.3 C10
owns allowlisted policy origin/effective-vs-requested evidence; M9 carries
privacy into evidence. M10.5 invalidates stale policy/placement evidence,
M10.6 re-resolves selected scope, M10.7 teaches config, M10.8 rechecks local
scope restoration. M11-M13 each define native settings/defaults/permissions
before experimental admission; M13.5 owns independent multi-context resource
and client/remote transfer precedence; M18 authored query cannot bypass.
M28 owns any new typed environment/CLI overrides and hard admin-limit
precedence before exposure; M29 shared conformance and promotion; M32/32.1
integration propagation/redaction; M40 hosted tenant quotas and authorization.
Every future adapter/deployment/capability expansion rechecks these outcomes,
including driver/executor/cluster scope where applicable. No requirement to
implement DuckDB fields or ratios on another engine. No new milestone/repo;
completed milestones remain closed unless actual prerequisite regression
requires targeted reopening. No gate satisfaction or runtime authorization.

## Historical approved M8.1.2 integration checkpoint (2026-11-26; reopened 2026-11-27)

The maintainer-approved detailed design is in [M8.1.2 approved prework](milestone-8-1-2-prework.md); it supersedes
historical footprint-driven resource decisions and earlier pending-design
statements. Design approval is not implementation or exit approval. Existing
runtime remains unchanged until implementation. M8.1.1 and targeted M7.4
correction are verified on main. No default database size or workload timeout;
optional authored footprint ceiling applies to all nine local project check
families. Native managed resource targets are not physical quotas. The
DuckDB-specific 25% memory and 10% disk reserve candidates require actual
combined calibration before default lock; no universal ratio. Required scope
and controls fail closed; optional estimate uncertainty is not a blanket block.
M8.1.2 owns B8 one-worker cancellation/confirmed exit/parent liveness, B9
native/IPC/owned scratch cleanup and crash-safe recovery, B10 serial per-check
worker and re-observation prerequisites. M8.2 owns remaining run-wide
lifecycle, deadlines, retry, cumulative resources and concurrency; M8.3 C10
publication. Preserve all future adapter applicability, type and scope gates.
No gate closed; separate implementation authorization required.

## Platform compatibility and future adapters

[Gate 4L P1-P6](execution-resource-safety-assignments.md#mandatory-platform-compatibility-and-graceful-degradation-gate-4l) requires capability-based permissive execution with actionable warnings and independently verified required protections, not runtime OS-version allowlists. M8.1.2 owns initial local native and persistent multi-version CI proof; M8.2/M8.3 preserve lifecycle and publication; M10/M10.7/M10.8 recheck readiness and guidance; M11-M13 experimental adapters, M13.5/M18, M29 and every future adapter/deployment/version expansion require applicable native proof and documented compatibility. M29 owns reusable shared conformance; M32/M32.1 preserves diagnostics in integrations. No new adapter or support range is implied.
