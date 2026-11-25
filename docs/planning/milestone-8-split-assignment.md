# Milestone 8 Split Assignment

## Scope and ordering

Split Decision: Required. The maintainer approved the implementation-bearing
split and the adapter-aware advisory direction. M8 is an umbrella, not an
implementation target. M8.1 -> M8.2 -> M8.3, then M9. The baseline is the
existing M7.4 runner/check engine plus the merged ecosystem roadmap. Do not
create parallel runners. This is the split assignment, not implementation
prework completion or permission to code. All three tracks are high-risk.

The canonical scope is the build order. ADR 0025 locks advisory safety and
ownership only; configuration syntax, estimates, schemas, thresholds and
lifecycle details must be decided in the owning prework. Research decision
for assigning scope: not required. Research before locking implementation:
required for unresolved estimate, configuration, lifecycle, schema and
publication decisions; evaluate necessity per decision. Record research
attribution privately.

## Split Assignment Matrix

| Assignment | M8.1 - scan-budget configuration and enforcement | M8.2 - execution planning and run lifecycle | M8.3 - result publication and CLI finalization |
| --- | --- | --- | --- |
| Implementation | Local policy settings and validation, non-executing evidence, Core admission, basic structured advisories and in-memory metadata. | Existing RunService execution plan, invocation ID, truthful timing and status/reason lifecycle, cleanup and scope metadata handoff. | Versioned local JSON, safe projection, atomic publication and stale-output policy, final summary and exit codes. |
| Non-goals | No production adapters, query endpoints, contract YAML policy, automatic scope/SQL rewrites, selector/sampling execution, results writer. | No new check semantics, selectors, writer, evidence or sink writes, alternate executor. | No evidence/failure-detail export, production result tables, state, external sinks, partial runs, selector execution or raw numeric exposure. |
| Risk/public surfaces | Config/CLI if admitted, adapter evidence, typed plan admission, diagnostics, existing capability behavior. | Run/check status and reason, service lifecycle, timing, placement, invocation scope, in-memory result interfaces. | Versioned result schema/path, artifact lifecycle, CLI/exit codes, diagnostics, privacy, scope/references, automation consumers. |
| Required gates | 4L primary; 4I/4A/4B/4C/4J as applicable; 3F2, 6, 8C scoped native-plan proof if touched; Gate 5E only if any existing writer is touched (no new result writer). | 5 primary; 4I/4L integration; 3F2, 6, 4J where adapter/profile handling touched; 1A/ADR 0014 prerequisite semantics; selector-readiness; sink metadata reservation only. | 5/5E primary; 3F2, 6, 4J where relevant; 4I/4L recorded metadata; selector-readiness; local-only sink metadata boundary under ADR 0022; 4O only if approximate values/derived differences proposed; 8 renderer publication requirements if referencing rendered SQL. |
| ADR/decision topics | ADR 0021/0025; safe local default and explicit limit, settings home/precedence, estimate evidence, hard versus warning admission, privacy and allowed recommendation classes; new ADR if durable config/adapter decision requires. | ADR 0014/0021/0022/0025; create run lifecycle/result semantics ADR using next available number, not occupied ADR 0021; run ID, timing, auto-compile vs existing artifacts, stale inputs, execution plan, aggregation, severity, cleanup, scope. | ADR 0022/0025 and lifecycle ADR extension or separate publication decision; versioned schema, field allowlist, artifact and sink refs, stale result policy, publish ordering, terminal/exit mapping and write failures. |
| Required docs | Config/CLI and scan policy docs, adapter interface/compatibility, check engine, testing, inventory/matrix and assigned prework. | CLI services, check engine/result model, architecture CLI/artifacts, compatibility and lifecycle ADR/prework. | Result model, artifact model, CLI/README/quickstart, diagnostics, compatibility inventory/matrix and versioning, testing, evidence boundary and prework. |
| Acceptance/conformance dimensions to expand before coding | A1-A9 below. | B1-B7 below. | C1-C9 below. |
| Responsibility-map rows to expand | Config loader validates user input only; adapter supplies non-executing evidence only; scan policy computes admission; RunService consumes proof before execution; advisory projection cannot modify plan. | Existing RunService owns orchestration and cleanup; engine owns check semantics; plan metadata owns intended scope; result models aggregate existing status taxonomy; no I/O writer in engine. | Dedicated Core artifact writer owns atomic publication/cleanup; allowlisted safe projection owns schema/redaction; RunService owns outcome coordination; CLI renders final result/exit category, not direct storage. |
| BDD/workflows | Valid bounded local run, unsafe/unknown/over-limit block, larger known-scope opt-in, advisory-only risk, unsupported suggestion no execution change. | Pass/fail/mixed run, no checks, prerequisite blocked, load/setup/execution/cleanup failures, truthful timing and preserved preflight. | Successful and failed checks generate trustworthy allowed artifacts, unsafe/write-failed path does not leave misleading output, consistent exit/terminal, suppressed sensitive payload, no external sink. |
| Required tests | Config/validation, real DuckDB scan guard and admission, service and check engine negative cases, no-scan spies, safe diagnostics, advisory invariant tests, preserve existing row-count/key/aggregate coverage. | Service/engine lifecycle and timing tests, ordering, dependency and mixed status tests, distinct connection failures, plan and scope, no generated results, preserve A tests. | Version/schema serialization, writer path and atomicity/failure/cleanup tests, privacy and CLI tests for every outcome, integration tests against real local adapter, carry forward A/B tests. |
| Phase exit | TDD RED/GREEN and fresh cumulative review against approved matrix; prove no capability shrink or accidental production claim; record carryover, docs and validation. | Same review; prove status/timing/cleanup and preserved admission/semantics, no writes. | Same review plus final umbrella coverage/orphan check, full required branch-wide validation, compatibility/changelog review and maintainer approval. |
| Blockers before coding | Split integrated; own prework, targeted research and user decisions locked; complete case matrix, source/responsibility map, BDD, test plan, DoD and approval. | M8.1 validated, own lifecycle design/ADR and matrix, scope/privacy/compile freshness decisions and approval. | M8.2 validated, own schema/privacy/writer/exit design and matrices, required gate proofs and approval. |

## Required acceptance row families and carryover

These are assignment families, not a completed dimension-expanded conformance
matrix. Each owning prework must enumerate concrete variants, exact expected
status/diagnostic and test references, and a rationale for non-applicable
cases. No row can be silently dropped.

| ID | Required family |
| --- | --- |
| A1 | Settings home, type, units, invalid/unknown keys, precedence and defaults; explicit limit versus computed status. |
| A2 | Zero-config known bounded local behavior and known-scope larger limit; no preservation of 64 MiB as a durable promise. |
| A3 | Non-executing trustworthy table/check estimate, conservative fallback, unavailable/unknown/untrusted/malformed evidence, units and provenance. |
| A4 | Over-budget, external relation/view, sidecar, executing plan mode, unsafe connection binding and capability states; no scan after hard block. |
| A5 | Scan volume versus returned rows/bytes and transfer volume; bounded result is not proof of bounded scan; distinguish available engine-native workload/cost evidence and unknown optional dimensions. |
| A6 | Advisory-only warning versus hard policy block; conditional indexing/pruning/pushdown/window/sample recommendations; no auto-rewrite, filtering, sampling, fallback or production claim. |
| A7 | Preserve currently supported row count, key safety and numeric aggregates, including precision, null/group presence and runtime transport; explicitly decide any proposed changed admission for row count, never narrow silently. |
| A8 | Safe diagnostics across config, metadata and adapter lifecycle; no sensitive identifiers, raw SQL/plan, credentials, values or native errors; unsupported recommendations marked future. |
| A9 | In-memory scan/advisory decision handoff; no generated artifacts, new sink, API stability claim or unbounded fetch. |
| B1 | Invocation identity and timing including failure/cleanup; current pre-engine finished timestamp corrected. |
| B2 | Explicit plan and artifact load/compile/freshness behavior; no automatic behavior without decision. |
| B3 | Pass/fail/warn/error/skipped/blocked/not_executable/no_checks and mixed precedence; prerequisite semantics. |
| B4 | Setup/engine/connection/cleanup failures, distinct versus repeated diagnostics, no masked primary failure. |
| B5 | Preserve A admission, capability and advisory evidence; no execution on hard block or hidden fallback. |
| B6 | Whole-project invocation scope with future selected-scope readiness, artifact/sink references only as allowed in memory. |
| B7 | Privacy-safe lifecycle/plan metadata and no result/evidence/state writes. |
| C1 | Versioned schema, path and invocation/timing/status/scope fields, backward/forward compatibility policy. |
| C2 | Allowlisted placement, adapter/capability, scan evidence and advisory fields, availability/reasons, no misleading claims. |
| C3 | Privacy matrix for every public field, diagnostic code/message/context/hint and raw values/keys/counts/diffs/SQL/plan/error text. |
| C4 | Pass/fail/error/warn/skipped/blocked/not_executable/no_checks, early failures, mixed outcomes and artifact-write failures. |
| C5 | Atomic publication, stale output, cleanup failures, unsafe paths/symlinks and invalid existing path shapes; no trustworthy-looking partial output. |
| C6 | Terminal counts/status and consistent exit mapping, diagnostic preservation, failure precedence, privacy. |
| C7 | Local artifact references and future sink placeholders only; no evidence/table/state writes. |
| C8 | Selector readiness: truthful full scope now, no subset implementation or false completeness. |
| C9 | All A/B regressions plus full final CI, capture decision advisory, pre-commit, cumulative review and compatibility/changelog assessment. |

Regression capture assignments: preserve stable gate IDs in the index, never
mark a deferred row covered merely because it is assigned. Review all matching
rows in each phase against trigger surfaces. For the currently deferred M8
primary-owner rows, assign these exact families:

| Capture row | Assignment |
| --- | --- |
| key-safety-duckdb-metadata-open-failure-adapter-diagnostic | A4/A8, B4, C3/C6 |
| duckdb-private-bounded-aggregate-transport | A7/A8, B5, C2/C3 |
| duckdb-private-typed-numeric-transport | A7/A8, B5, C2/C3 |
| aggregate-native-service-lifecycle | A4/A8, B4, C3/C6 |
| aggregate-core-result-privacy | A7/A8, B7, C3 |
| aggregate-native-service-group-presence | A7, B3/B7, C3/C4 |
| yaml-diagnostic-redaction | A1/A8, B2/B7, C3/C6 |
| yaml-profile-and-source-privacy | A1/A8, B4/B7, C3/C6 |
| aggregate-service-output-privacy | A8/A9, B7, C2/C3/C5/C6/C7 |
| compiled-artifact-yaml-loader-diagnostics | B2/B7, C3/C4/C5 |
| compile-command-terminal-contract | C6/C9 (preserve existing compile behavior) |

The three primary-owner gates are diagnostics_privacy_carryover,
artifact_publication_carryover and cli_behavior_carryover. Adapter-testkit,
check-engine and parser/compiler carryovers also apply when those surfaces
are touched. The first phase must review existing scan/runtime captures; the
last phase verifies all assignments and remaining future dispositions.
No change to capture status is authorized by this planning artifact.

## Later advisory ownership

M12.5 owns richer metadata/plan-driven recommendations; M11-M13 experimental
PostgreSQL/Snowflake checkpoints own scoped engine-specific evidence and
advisory proof subject to pre-creation gates. M29 owns official shared
conformance, including distinct scan/result/transfer dimensions and native
cost/workload indicators, supported/unsupported/unknown evidence, privacy and
no silent scope change. M18 owns query endpoints, M24/M25 explicit sampling
and state/windows, M31 bounded advanced evidence; advisory references do not
pull their implementations forward.

## Orphan check and next work

The previous combined build items (execution plan, run service, policy,
run-results artifact, placement/capability/scope/budget metadata, refs, exit
codes and terminal summary), all listed gates and required tests are
assigned above to implementation-bearing tracks. Cross-cutting gate and ADR
requirements apply to every affected track. No umbrella-only implementation
is authorized. Each sub-milestone's detailed prework must finish its
dimension-expanded matrix, responsibility/source map, BDD, exact tests,
research decision, ADR and docs alignment, DoD and exit review before coding.
Recheck gate attachment index, compatibility, current files and captures at
each prework/exit. If an omitted requirement or conflict is found, block and
correct the split assignment, not invent a scope decision.

Next: integrate split documentation, then M8.1 research/design prework.
Resolve concrete settings, evidence and admission/advisory questions before
implementation. No experimental repo is due during these phases; keep
checking ecosystem checkpoints. No milestone prework is declared satisfied.
