# Ecosystem Roadmap

## Purpose

Recon should start as a focused open-source core and grow into an ecosystem.

The ecosystem should not be created too early, but the core should be designed so it can support adapters, packages, integrations, and Hub later.

## Core repo

`recon-core` remains the source of truth for:

- product model,
- contract schema,
- parse/compile/run behavior,
- artifact model,
- check result model,
- adapter interface,
- package rules,
- validation rules.

## Adapter ecosystem

Long-term adapter packages:

```text
recon-duckdb
recon-postgres
recon-mysql
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

DuckDB currently starts as an in-core local development adapter installed with
`recon-core[duckdb]`. A separate `recon-duckdb` package should wait until the
adapter API and shared adapter test kit stabilize.

Official external adapter releases and stable compatibility claims remain
Post-MVP Milestone 29 work. Earlier experimental repositories are permitted
only through the staged incubation checkpoints below and the applicable
adapter conformance prework. Until the official gate is satisfied, DuckDB
remains the in-core local development adapter; `recon-duckdb` is an extraction
candidate, not an early split. See [ADR 0024](../decisions/adr-0024-staged-ecosystem-incubation.md).

Adapter packages should own:

- connection,
- SQL dialect,
- metadata access,
- schema introspection,
- type mapping,
- hashing behavior,
- capability declarations.

Adapter packages should not own reconciliation semantics. `recon-core` owns
typed check plans and comparison meaning; adapters render or execute those
plans for a specific system.

Adapter packages should declare their supported adapter API version.

Adapter compatibility claims must be granular. An adapter may support current
rendering without claiming stable execution, broad placement,
materialization/staging, result/evidence sink writes, production result tables,
or probabilistic key-summary behavior.

Production adapter execution claims must also wait for native SQL optimization
and dialect validation conformance. The shared adapter test kit should prove
typed-operation rendering, adapter-native SQL snapshots, dialect validation
where useful, semantic execution behavior, blocked unsupported placement, and
privacy-safe diagnostics before an adapter is documented as production-ready for
warehouse-scale execution.

Production result-table and evidence-sink support through adapters must wait
for Post-MVP Milestone 25.5 result-table/sink design and Post-MVP Milestone 29
adapter write/sink conformance. Source, target, or third-connection
destinations are allowed only when explicitly configured and proven by adapter
capability tests.

Probabilistic key-diff support, including Bloom-filter-like summaries or other
set sketches, must wait for Gate 4K and Post-MVP Milestone 29 adapter test-kit
conformance for summary build, serialization, transport or storage, probing,
reverse probing when needed, metrics, privacy, and cleanup.

Experimental adapters can be useful for learning, but they must not claim
stable execution compatibility, sink compatibility, table-sink compatibility,
or probabilistic-summary compatibility until the relevant conformance gates are
implemented and passing.

## Adapter test kit

Future repo:

```text
recon-adapter-testkit
```

Purpose:

- validate adapter behavior,
- validate adapter API version compatibility,
- standardize capability tests,
- test metadata behavior,
- test SQL rendering for typed plan operations,
- test native SQL optimization and dialect validation for claimed execution
  capabilities,
- help community adapter maintainers.

Adapter test kit should appear after the typed check-plan and base adapter
interfaces stabilize. Its first compatibility suite must include
the Adapter/Profile Diagnostic Conformance Gate from
`docs/compatibility/adapter-api.md` before external adapter repos are published
or treated as compatible. That conformance must prove that adapter factory
exceptions, capability declaration exceptions, adapter metadata exceptions, and
adapter-provided diagnostics cannot leak rendered profile keys or values into
CLI output, artifacts, run results, evidence, reports, logs, failure details, or
test snapshots. It must include literal adapter `type` routing, including
rejection of templated `{{ ... }}`, `{% ... %}`, `{# ... #}`, or
`env_var(...)` `type` before adapter resolution, plus rejection of
factory-returned adapter metadata that differs from the literal profile `type`,
public/shared rendering helper cases where a supplied renderer's
`adapter_type` is missing, malformed, exception-raising, or different from the
resolved adapter type and therefore fails before rendering,
diagnostic-code cases where unsafe config keys or rendered values are embedded
in delimiter-separated or separatorless forms, such as `RC_PASSWORD_LEAK`,
`RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`, before the shared test
kit or external adapter repos claim compatibility. It must also prove safe
adapter diagnostic codes with incidental non-secret config-key substrings, such
as `RC_ADAPTER_CAPABILITY_UNSUPPORTED`, are preserved.

## Check and policy packages

Future official packages:

```text
recon-checks-cdc
recon-checks-migration
recon-checks-medallion
recon-policies-sampling
recon-policies-tolerances
recon-evidence-templates
```

These packages should provide reusable standards while keeping private project mappings out.

## Schema policy packages

Schema policy packages may provide common technical-column ignore rules.

Examples:

- replication service metadata columns,
- managed ingestion metadata columns,
- change-event metadata columns,
- ingestion audit columns.

These should remain explicit. Installing a package should not silently ignore columns unless a user references the policy.

## Recon Hub

Future repo:

```text
recon-hub-index
```

Initial Hub can be a static index of packages and adapters with metadata.

Possible categories:

- adapter,
- check pack,
- sample policy,
- tolerance policy,
- schema policy,
- evidence template,
- example project,
- domain package.

## Integrations

Future integrations:

```text
recon-orchestrator
recon-workflow-provider
recon-github-action
```

These should come after the CLI and artifacts are stable.

## Agent and local tool ecosystem

Future user-facing agent support should start with one canonical Recon agent
instruction pack for users' own data projects. Tool-specific wrappers should be
generated from that source of truth so agent rules do not drift. The installer
should use safe merge, skip, overwrite, update, and doctor behavior before it
writes files such as `AGENTS.md`, `llms.txt`, `.recon/agent/...`, optional
tool-specific wrapper folders, or later local tool configuration.

An optional local Recon MCP server or structured agent tool interface should
wait until the CLI and Python command surfaces it wraps are stable. The first
tool surface should be local-only, safe-by-default, mostly read-only, redacted,
and approval-gated for row scans, file writes, contract edits, and remediation
actions.

## Event export and remediation integrations

Lineage, observability, catalog, orchestration, and event exports should be
metadata artifacts. They should link back to Recon run results and evidence
without exporting raw rows, keys, values, credentials, rendered profiles, raw
SQL, or native database errors by default.

Workflow actions such as webhooks, tickets, notifications, remediation hooks,
contract edits, threshold updates, table tagging, or downstream filtering should
be approval-first. They need dry-run behavior, idempotency, retries, audit logs,
rollback semantics, permissions, and non-destructive defaults before any
integration treats them as supported.

## Semantic and AI package ecosystem

Semantic, vector, fuzzy, model-judged, or assistant behavior should live in
optional packages first, not default `recon-core` behavior. These packages must
keep exact reconciliation distinct from non-exact similarity, record model and
prompt versions when models are used, bound cost and privacy risk, validate
structured output, and require explicit user approval before generated changes
affect contracts, actions, baselines, or evidence.

## Documentation site

Docs may eventually move into:

```text
recon-docs
```

Only split docs after the core documentation becomes too large for the core repo.

## Examples repo

Large end-to-end examples may eventually move into:

```text
recon-examples
```

Keep small examples in `recon-core` until the examples become heavy.

## Community contribution path

Community contributors should be able to contribute:

- docs,
- examples,
- checks,
- adapters,
- policy packages,
- evidence templates.

The contribution process should favor small, tested, well-documented changes.

## Repository introduction checkpoints

[Resource-safety assignments](execution-resource-safety-assignments.md) apply at every adapter and test-kit checkpoint. Native resource controls, truthful estimates and cancellation/cleanup are capability-specific prerequisites, not optional polish.

The following is the canonical milestone-to-repository recommendation schedule.
These are dependency-aware parallel work candidates, not new numbered
milestones, guaranteed delivery dates, automatic repository creation, or
permission to expand the current milestone. Each candidate needs an explicit
maintainer decision and its own applicable prework before implementation.

| Checkpoint | Candidate repositories or packages | Recommendation and prerequisites |
| --- | --- | --- |
| M10 exit / 0.1 release-readiness | `recon-core` | Finish the end-to-end MVP, including results, evidence, examples and the release decision. Review the next ecosystem candidates; do not create experimental repos before that decision. |
| M10.5-M10.7 | `recon-adapter-testkit` | Recommend an experimental shared suite as a parallel track. Inventory carryover rows, lock test-kit packaging and the applicable Gate 8 conformance matrix and pre-creation proofs, then extract reusable tests against an exact Core revision. Keep in-core tests until equivalent coverage is demonstrated. Inventory resource evidence/control/cancellation conformance. |
| M11-M12 | `recon-postgres` | Recommend the first experimental external SQL adapter after the test-kit baseline is usable. Prove connection/lifecycle, metadata, typed rendering, capability rejection and only explicitly admitted bounded semantic execution. Assess operational database workload, trustworthy non-executing plan evidence, bounded transfer and actionable advisories under ADR 0025. Prove operational load safeguards, statement timeout/cancellation, native estimated cost units, concurrency and transfer bounds. |
| M12-M13 | `recon-snowflake` | Recommend a second experimental adapter after the first external adapter demonstrates the shared contract. Require isolated synthetic fixtures, scan/cost controls, dialect and numeric/type proof, including warehouse-specific plan/pruning evidence, cost-unit limitations and bounded transfer under ADR 0025. Prove warehouse-specific scan/partition/credit evidence limitations, native resource limits, timeout/cancel and warehouse selection/workload controls. |
| M16-M16.5 | `recon-checks-migration`, `recon-policies-tolerances` | Recommend initial experimental resource packages only after the relevant resource schemas, precedence, expansion and dependency/lock rules are implemented. No official release claim. |
| M26-M27.5 | `recon-checks-cdc` | Recommend a candidate CDC package after the applicable CDC semantics and resource model are proven. |
| M29 | `recon-adapter-testkit`, `recon-duckdb`, `recon-postgres`, `recon-snowflake` | Complete official cross-repo test-kit, packaging, release and migration gates; extract DuckDB only after its extraction gate. Promote experimental adapters only for independently proven capability families. Require shared resource-envelope, native controls, workload evidence, cancellation/cleanup and performance/scale conformance. |
| M29 onward | `recon-bigquery`, `recon-databricks`, other adapter candidates | Recommend additional adapters based on actual demand and capability-specific conformance, not an automatic bulk repo rollout. |
| M32 | `recon-hub-index`, `recon-github-action`, `recon-airflow` | Recommend index and CI/orchestration integration repos once package, CLI, artifact and compatibility contracts are stable. |
| M32.2 | `recon-mcp` | Recommend an optional local tool repo only after tool schemas, permissions, privacy and scan/action safety gates are resolved. |
| M38 | Official check/policy/evidence packages | Publish supported versions only after package compatibility, Hub metadata, tests and release process are ready. |
| M39 | `recon-docs`, `recon-examples` | Recommend a split only when maintenance benefits justify independent release/CI overhead. |
| M42-M42.5 | Optional semantic packages, `recon-ai` | Recommend separate packages only after semantic/AI, privacy, cost, evaluation and approval gates are met. |

At each milestone entry, phase exit and next-work recommendation, review this
schedule for the current and next milestone, plus any previously deferred
candidate. Report the candidate, readiness evidence, dependencies, missing
gates, and disposition: recommend now, already satisfied, defer with rationale,
or blocked. Include parallel repository work in the proposed next steps when
ready. Do not silently drop a deferred recommendation. Check whether the repo
already exists before proposing creation. Do not create, publish, or transfer
code without approval.

### Experimental adapter admission

Early test-kit and adapter repos are development experiments, not official
external releases. Before creating or splitting a test-kit repo, satisfy the
existing pre-creation requirements in the adapter API compatibility document
and Gate 8, including the diagnostic and artifact-publication conformance
gates and defined API/SQL matrices. Before an experimental adapter is created,
establish the applicable test-kit baseline, lock the scoped dependency and
registration approach, identify supported and unsupported capability families,
and prove applicable safety gates using isolated synthetic data. Do not defer
privacy, capability rejection, scan safety, or artifact integrity just because
a repo is experimental. Required semantic CI must install the dependency and
fail on missing dependencies, not silently skip.

Pin experiments to a known Core commit or explicit pre-release version. Record
the Core/test-kit/adapter revision combination, capability-specific evidence,
limitations and regression capture dispositions. Use only supported extension
boundaries; if an experiment exposes a missing or private Core extension
boundary, propose the Core-owned design change separately under normal
prework rather than import private DuckDB internals or duplicate semantics.
Do not claim stable API ranges, general execution, production workloads,
cross-context placement, sink support or probabilistic support from a prototype.
The official adapter gate remains unchanged.

## Ecosystem sequencing

Recommended order:

1. stabilize `recon-core`,
2. stabilize contract schema,
3. stabilize parse/compile/run artifacts,
4. stabilize adapter interface,
5. add the user-facing agent onboarding pack after the public local workflow is
   stable,
6. incubate the shared adapter test kit and first experimental adapters after
   the MVP decision, subject to their pre-creation gates,
7. split `recon-duckdb` and promote official adapters only after adapter
   conformance gates are satisfied,
8. incubate reusable resources after their loaders are implemented; publish
   official check/policy packages only at the official release gate,
9. create Hub index,
10. add metadata event exports after result and evidence metadata is stable,
11. add optional local tool interfaces after the wrapped command surfaces are
    stable,
12. create orchestration integrations,
13. add action/remediation integrations only after approval, audit, and privacy
    gates are satisfied,
14. add semantic and AI packages last, as optional non-default ecosystem
    packages.

## Ecosystem principle

Do not create many repos before the core concepts are stable.

Design for the ecosystem early, but split when there is real code, real tests, and real users.

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is implemented and verified on main (PR #38). Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

## Mandatory adapter-specific resource conformance

Apply [Gate 4L adapter-specific resource applicability and proof](execution-resource-safety-assignments.md#mandatory-adapter-specific-resource-applicability-and-proof) at M11-M12 PostgreSQL, M12-M13 Snowflake, M13.5 remote/cross-context, M29 official test-kit/promotion and every later candidate, version or capability expansion. Resolve R1-R10 before scoped admission and reprove at promotion. No automatic adapter rollout or new scheduled milestone.
