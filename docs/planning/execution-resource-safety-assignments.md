# Execution Resource Safety Assignments

## Current redesign checkpoint (2026-11-27)

M8.1.2 implementation is suspended. The [reopened prework](milestone-8-1-2-prework.md#current-status-whole-design-reopened-2026-11-27)
controls next work. R1-R10, A1-A13 and P1-P6 remain outcome obligations;
B8-B10 mechanism-specific assignments are reopened, not waived. Prior approved
worker, exhaustive native observation and automatic recovery requirements below
are historical mechanisms pending explicit replacement dispositions. Prefer
native controls, standard maintained APIs and the smallest proven mechanism.
Neither shared execution resources nor missing optional observation alone
justifies refusal. Require demonstrated benefit and scope-specific necessity
before custom OS-level management in any future adapter; preserve actual
noninterference, exact binding, privacy, no unrelated deletion, explicit
control enforcement and truthful error/cleanup outcomes. M8.2, M8.3, M9.5,
M10.8, M29 and subsequent adapter obligations retain their owners. No coding
or gate closure until revised prework and separate approval.

## Consolidated replacement proposal (approval pending)

The [consolidated native-first replacement design](milestone-8-1-2-prework.md#consolidated-native-first-replacement-design-proposed-for-approval-2026-11-27)
proposes the same guarded native read-only execution path for standalone
and embedded usage in M8.1.2, no mandatory subprocess, six logical adapter-scoped
settings with maintainer-approved memory/spill percentage modes,
adjustable adapter-local memory/spill heuristics and minimal
private scratch. Native configuration-conflict limitations and remaining
implementation proof (including Windows baseline WAL regression) are
explicit. Prior provisional mechanism proposals below are historical
where inconsistent. No gate closure or implementation authorization.

Automatic, explicit percentage of freshly observed available capacity, and
fixed MiB modes are independent for memory/spill; each logical setting
has exactly one mode. CPU remains automatic or fixed threads. Explicit relative
requests cannot silently degrade when their denominator is unknown; automatic
missing optional facts remain advisory when safe. Recompute at each check,
not during it. Elastic capacity, arithmetic, missing/zero evidence, native
control effects and both execution modes require proof. Future adapters assess
native-appropriate relative and absolute controls, not universal DuckDB syntax.



## Adapter-scoped execution policy and precedence (proposed; approval pending)

The current resource configuration proposal is adapter-scoped project defaults,
selected profile target adapter defaults, and selected target named connection
overrides, in that order after adapter defaults. Operational policy stays out
of connection identity/factory payloads, credentials and comparison contracts.
Resolve each logical setting atomically, with explicit reset to automatic or
absent; no generic deep merge or global engine-specific default. Unreferenced
policy values and inactive targets do not affect selected work; validate
applicable policy, adapter namespace, connection names and conflicting same-
context aliases before affected data reads. Preserve existing binding and
profile-selection/redaction, plain parse/compile and public API. No new generic
adapter method, shared native setting syntax, or hard quota guarantee.

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

## Proposed outcome mapping (approval pending)

Maintainer scope decision (2026-11-27): M8.1.2 owns adaptive resource
management for both standalone and embedded Python usage. No deferral of
embedded adaptation or replacement admission to M8.2. Preserve shared
application safety and current API capabilities; prove the smallest native-first
mechanism without automatically restoring per-check workers, custom IPC or
OS ownership inspection. M8.2 retains full invocation lifecycle and cumulative
resource responsibilities. Exact mechanism and remaining scope dispositions
are not approved yet.

The [native-first redesign proposal](milestone-8-1-2-prework.md#native-first-redesign-proposal-2026-11-27-approval-pending)
records the tested ordinary invocation alternative and explicit A1-A13,
R1-R10, B8-B10 and P1-P6 dispositions. Preserve outcomes; do not resume
historical mechanism implementation. Embedded execution is mandatory in M8.1.2;
removal of reserve leaves/automatic recovery/worker infrastructure and
pressure polling require maintainer approval. M8.2 full invocation lifecycle
and cumulative/concurrency obligations and all later adapter gates remain.

## Historical gate and status (mechanisms reopened)

[ADR 0026](../decisions/adr-0026-local-execution-policy-and-scan-admission.md)
has an approved adaptive resource amendment; see [M8.1.2 approved prework](milestone-8-1-2-prework.md). Do not implement the historical footprint-driven policy. Current runtime is unchanged until approved implementation. ADR 0025 and existing binding, placement, privacy and
no-silent-scope-change rules remain requirements. Gate 4L owns resource
safety and admission; Gate 4I placement/transport, Gate 5 lifecycle, Gate 5E
output/cleanup, Gate 3L profiling and Gates 8/8C adapter conformance.

Every affected milestone must expand assigned families into exact acceptance
variants, diagnostics, test nodes, BDD, responsibility map, DoD and exit
proof. No readiness or exit with unassigned applicable requirements. Recheck
any added/moved execution, profiling, movement, write, cache or concurrent
work, even if not listed. Historical completed phases remain unchanged;
carry forward regressions when touched.

| ID | Requirement | Primary implementation ownership |
| --- | --- | --- |
| R1 | Independent physical footprint, estimated input, scan/work/intermediate cardinality, returned rows/bytes, transfer, actual observations and configured controls; provenance, units, availability, uncertainty. Unknown never zero. | M8.1 local; M11-M13 native; M12.5 richer analysis; M29 |
| R2 | Hardware/environment availability: RAM/CPU/cgroup/container constraints, disk/headroom, concurrent use; missing/misleading host information is not safety proof. P1-P6 platform compatibility apply. | M8.1; M11-M13; M29; all affected expansions |
| R3 | Native memory/thread/spill controls and bound read-only execution, enforcement capability, failure, configuration precedence, isolation/restoration; distinguish engine-managed memory from actual process ceiling. | M8.1; M11-M13; M29 |
| R4 | Useful measured defaults and explicit overrides; optional footprint cap considered separately, no arbitrary low threshold or unsupported hardware ratio. Larger safe workload versus small costly workload. | M8.1; M10; M29 |
| R5 | Non-executing actual binding and operation-aware admission, required scope fail closed, no executing plan preflight, hidden fallback, implicit filtering/sample or escalation. | M8.1; all execution expansions |
| R6 | Deadline/timeout, cancel requested vs confirmed stopped, interrupted/failed/not-executed outcome, cleanup and retry. M8.1 proves any control it relies on before admission. | M8.1.2 worker stop/confirmed exit and cleanup prerequisite; M8.2 remaining lifecycle/deadline/retry; M11-M13; M29 |
| R7 | Per-check and cumulative run resources, repeated scans, concurrency/fan-out; safe scheduling and budget scope. | M8.1.2 per-check serial worker/re-observation prerequisite; M8.2 cumulative/concurrency; selectors/packs/profiling/state/integrations |
| R8 | Safe metadata handoff and durable projection, effective policy vs observed use, availability/provenance and resource outcomes, no raw plans/paths/data. | M8.1-M8.3; M9/31/32.1 |
| R9 | Evidence-based optimization advice: join growth, skew, width, repeated scans, pushdown/index/pruning, subset/window/sample, coverage tradeoffs; no automatic changes. | M8.1 basic; M12.5 deeper; M24/25 actual modes |
| R10 | Reproducible bounded synthetic scale/performance and failure probes across versions and resource envelopes; no universal guarantee or fixed SLA from probes. | M8.1 design/exit; M10; M10.5-10.7; M11-M13; M29 |

## Milestone checkpoints

| Milestone | Mandatory application |
| --- | --- |
| 9 | Budget evidence retrieval, export/movement, memory/disk and cleanup independently of output size. |
| 10 | MVP readiness requires useful zero-config and explicit-limit behavior on representative constrained/capable environments, larger-than-RAM cases where supported, and honest limitations. |
| 11 | Prove metric/group intermediate workload and native PostgreSQL operational safeguards at experimental checkpoint. |
| 12 | Distinguish metadata-only from scanning and bound catalog fan-out; prove native adapter metadata/resource capability. |
| 13 | Prove mapping/cast/width workload impacts and Snowflake warehouse-native resource, pruning and billing evidence at experimental checkpoint. |
| 15 | Reassess macro-generated operations and prohibit policy bypass. |
| 18 | Prove authored query read-only scope, non-executing evidence, binding and enforcement. |
| 19 | Recompute selected-scope and cumulative work; no hidden subset. |
| 21 | Prove join multiplicity, intermediate work, resource controls and bounded movement/detail. |
| 22 | Assess normalization and timestamp workload and pruning. |
| 23 | Budget hashing, canonicalization and confirmation workload. |
| 24 | Budget sample construction as well as comparison; sample size is not scan size. |
| 25 | Budget bootstrap, incremental windows, state reads/writes and samples; no silent full-scan fallback. |
| 26 | Bound CDC window scans, key movement, summaries and exact confirmation. |
| 27 | Bound asymmetric delete comparisons, state and transfer. |
| 28 | Resource CLI overrides require explicit precedence, validation and enforcement; debug cannot bypass. |
| 29 | Finalize shared version-specific native controls, evidence, resource envelopes, timeout/cancel/cleanup, bounded transfer/spill, useful defaults, unsupported cases and performance regression conformance before adapter promotion. |
| 30 | Budget JSON/nested expansion, width and extraction. |
| 31 | Bound export queries, rows/bytes, pagination, memory, disk, network and cleanup. |
| 32 | Integrations preserve budgets, retry/concurrency and cancellation semantics; no bypass. |
| 34 | Budget multi-grain fan-out and repeated comparisons. |
| 37 | Bound remote state I/O, retention, lock and retries. |
| 40 | Prove hosted tenant isolation, quotas, concurrency, cancellation and fair allocation separately. |
| 42 | Budget semantic expansion and generated comparisons. |
| 8.1.1 | Binding preflight and owned execution context; interim existing key/SUM footprint guard only. Binding portions of R3/R5/R6/R8/R10; no new resource defaults. |
| 8.1.2 | Approved design; implementation in progress, exit pending. Own remaining R1-R10/A1-A13, measured defaults, optional footprint ceiling, non-executing evidence and verified native controls; B8 stop/exit/parent liveness, B9 worker/native/IPC/scratch cleanup and recovery, B10 serial per-check resource scope. Candidate tuning requires native exit proof. See [M8.1.2 approved prework](milestone-8-1-2-prework.md). |
| 8.2 | Own remaining B8-B10 invocation deadlines/timeouts, cancellation and retry lifecycle, run-wide cleanup, cumulative resource budgeting and bounded concurrency; reuse M8.1.2 prerequisite controls, no duplicate executor. |
| 8.3 | Publish allowlisted resource policy, actual versus estimated use, unavailable versus zero, enforcement and timeout/cancel/cleanup outcomes; C10. |
| 10.5 | Invalidate stale admission evidence, including policy, binding and environment changes. |
| 10.6 | Recompute admission and cumulative work for actual selected scope. |
| 10.7 | Teach resource settings, limitations and safe override behavior in onboarding. |
| 12.5 | Implement richer workload/plan analysis and evidence-backed recommendations, including cardinality/skew, join growth, repeated scans, widths, indexing/pruning, bounded profiling and explicit subset/window/sample coverage tradeoffs. |
| 15.5 | Budget expanded check packs and repeated work. |
| 24.5 | Budget combined sampling policy expansion and repeated work. |
| 25.5 | Bound sink writes, batches, retries, movement and cleanup. |
| 25.6 | Budget repeated profiling, history/drift scans and retention. |
| 25.7 | Budget rollup refresh/fan-out; no misleading completeness. |
| 27.5 | Bound propagation/fan-out and confirmation. |
| 32.1 | Publish only allowlisted resource evidence and bounded event transport. |
| 32.2 | Agent tools respect policy, cancellation and bounded outputs. |
| 32.5 | Budget action retries/fan-out separately; no unapproved mutation. |
| 42.5 | Budget AI-suggested execution/tool fan-out; suggestions do not authorize scans. |

## Historical reopened design prerequisites (superseded by approved checkpoint below)

Research official native settings and version limits, hardware/container
availability, memory outside engine buffer management, spill disk limits,
timeout/cancel feasibility, actual typed SQL and safe admission. Preserve
existing binding evidence. Benchmark authorized bounded synthetic small and
larger, compressed/uncompressed, skewed/grouped/repeated-scan/row-count
workloads across supported pins and available constrained/capable envelopes.
Measure footprint, estimated input, elapsed time, reliable process memory,
temporary disk, control effects and cleanup; document fixture truth, units,
limitations and unavailable evidence. Never use executing inspection as
production preflight. Use authorized temporary CI fallback under standing validation policy,
isolated fixtures and cleanup if local execution unavailable.

Compare optional footprint cap, hardware-aware defaults, explicit resource
envelopes and native enforcement; decide unknown/unsupported cases and
warning versus hard admission. No arbitrary replacement number. Determine
which timeout/cancellation controls are M8.1 prerequisites versus M8.2
lifecycle; reassess split. Record sources and experiments privately.
Present concrete proposed settings, defaults, compatibility and remaining
questions for approval, then revise ADR 0026, A1-A13 matrix, BDD, owner map,
test plan, DoD and implementation plan. Integrate approved prework before
implementation authorization. No new repository, implementation or
gate satisfaction is authorized here.

## Mandatory M9.5 delivery checkpoint

M9.5 mandatory type compatibility retrofit: assess R1/R3/R5/R7/R9/R10 for conversion and canonical key workload, intermediate growth, metadata binding, pruning, aggregate arithmetic, scheduling and supported-version scale; re-evaluate other R families when touched. M9.5 cannot bypass M8 admission or claim type proof as resource proof. See [type compatibility assignments](type-compatibility-assignments.md).

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is implemented and verified on main (PR #38). Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

## Historical M8.1.2 resource policy handoff (superseded by approved checkpoint below)

M8.1.2 is the mandatory implementation owner of the reopened resource/default
design, not an optional later optimization. Execution order: M8.1.1
binding preflight (what will actually run) -> verified targeted M7.4
grouped SQL correction -> M8.1.2 resource preflight/admission (whether
the bound workload may run under effective policy) -> M8.2. M8.1 cannot
exit until both children and the correction are verified. M8.1.1 retains
the legacy 64 MiB key/SUM-only guard temporarily; neither it nor earlier
40/20 MiB proposals or experimental control values are approved defaults.
No footprint-derived universal workload ceiling, arbitrary replacement
threshold, or blanket rejection solely because an advisory estimate is
unknown. Scope proof and proven enforceable safeguards remain mandatory;
unknown required safety evidence fails closed. Reassess admission by
operation and actual available RAM/CPU/container/disk/headroom, explicit
user limits, engine-specific control guarantees and workload evidence.
Prove useful zero-config behavior for representative capable and constrained
machines, larger safe files/workloads and small expensive workloads, across
the pinned versions; avoid unnecessary restrictions without weakening safety.
Distinguish estimates/advisories, physical footprint, actual resource use,
bounded transport and engine/process controls. No executing production
preflight, silent sampling or fallback. Resolve R1-R10 and A1-A13, including
calibrated defaults, override precedence, unknown/unsupported cases,
native-control limits and earlier required cancellation/containment.
Use corrected actual Recon SQL and previous private research/CI evidence;
do not infer defaults from earlier experiments. If M8.2 protections are
required for admission, explicitly pull them forward with approved split
changes. Exact settings, thresholds, controls and detailed M8.1.2 prework
remain open; separate design approval, implementation and native exit proof
required.

## Mandatory adapter-specific resource applicability and proof

Resource safety is a shared policy and evidence contract, not a shared
engine implementation. Core owns common admission, precedence, required
protection, outcomes and safe evidence semantics. The adapter owns native
capability discovery, actual execution location, settings and measurements,
control effects, permissions and cleanup. Treat client transport, local,
remote and distributed execution as independent resource scopes.

Maintainer-approved direction: adaptive, adapter-aware, minimally restrictive
defaults with portable best-effort local protection and conditional isolation.
Hard guarantees require verified enforcement at the requested scope; never
silently downgrade a hard requirement. Preserve native spilling and safe
larger-than-memory work; account for scratch headroom and cleanup.
No universal CI-derived caps, fixed ratios or DuckDB-specific mechanisms
imposed on other engines. Use actual environment, workload, capabilities
and explicit user/admin constraints. Optional unknown estimates alone do
not block independently proven required protection. Resource failure is
not a reconciliation mismatch. No implicit sampling, relaxed retry,
additional transfer, engine switching, privilege escalation or unauthorized
shared infrastructure changes.

Before scoped experimental admission of any new adapter, version, operation,
deployment or placement, and again before official promotion or capability
expansion, review every R1-R10 family. Record applicability, execution
scope, native mechanism or alternative proof, units and control scope,
permission/version/environment constraints, effective enforcement versus
advisory or unknown evidence, expected outcomes, concrete positive and
negative test nodes, owner and recheck milestone. Keep enforced,
best-effort/advisory, unsupported, unknown and not applicable distinct.
Non-applicability requires a rationale; missing APIs alone do not justify
it. Required unproven protection blocks only the affected capability;
approved alternative proof is allowed. Deferred mandatory proof is a
blocker for that capability, not an exit waiver. No universal setting names
or new public schema are authorized by this rule.

| Checkpoint | Additional mandatory adapter-specific proof |
| --- | --- |
| M8.1.2 DuckDB | Actual hardware/container/scratch scope, native controls and spill across supported versions, disk-backed larger-than-memory work, low/full disk, setting interference/isolation, readback versus effect, cancellation prerequisite and scratch cleanup; safe larger files and costly small compressed inputs independently. |
| M8.2 / M8.3 | Remaining run-wide resource/cancellation/cleanup lifecycle; safe publication of effective policy and actual outcomes. |
| M10 / M10.8 | Useful zero-config and explicit overrides on constrained/capable environments; reprove restored/expanded local scopes. |
| M11-M12 PostgreSQL experimental | Server/session/transaction and permission-specific controls, per-operation and parallel-worker memory multiplication, temporary file limits, operational workload, timeout/confirmed cancellation, settings restoration/pool isolation, bounded client transfer. |
| M12-M13 Snowflake experimental | Assigned warehouse/role, queue/concurrency, scan/pruning evidence, credit/billing attribution and quota limitations, native timeout/cancellation, bounded client transfer. No automatic resize or shared monitor modification. |
| M13.5 / M18 | Actual remote/cross-context placement and transfer budgets; authored query admission, binding and native protection for actual operations. |
| M29 | Capability-specific shared test-kit contract and native proof before promotion; all supported versions, deployment/permission limits, unsupported cases, actual resource/cleanup and performance regressions. |
| M29 onward, every new adapter candidate | Same pre-creation, scoped admission, release and expansion gates. Distributed engines require separate driver/executor/cluster resources, shuffle/spill, skew, scheduler allocation, task retry/fan-out and remote cancellation where applicable. No new engine support or milestone assumed. |

At implementation capture actual resource regressions in existing
regression-capture metadata with reproducible test nodes, scoped proof
and adapter-testkit carryover. M8.1.2 must address oversized-safe workload,
compressed-costly workload, spill-limit readback/effect mismatch, global
setting interference and cleanup. M29 retains native regressions and tests
shared invariants with engine-appropriate fixtures. Later adapter regressions
require equivalent owner, gate, proof and recheck assignments. Existing
metadata and branch-wide advisory checks remain mandatory; passing metadata
or benchmarks alone does not establish gate satisfaction. Reuse existing
planning/capture mechanisms, not a parallel tracker.


## Mandatory platform compatibility and graceful degradation (Gate 4L)

Maintainer-approved framework rule: **permissive when independently safe,
protective when required, explicit about uncertainty**. An untested or newly
released OS, architecture, dependency, engine version or deployment is not
by itself a runtime admission failure. Test coverage/certification is not
a runtime version allowlist. Discover actual capabilities and evidence at
the execution scope; never substitute version strings for actual proof.
Distinguish verified protection, best-effort observation, optional unknown,
unsupported, invalid evidence and not applicable. Keep trustworthy partial
facts even if another probe fails. Unknown is not zero or unlimited.
Use verified equivalent alternatives when available without expanding
scope or changing comparison semantics. No silent fallback, new fixed
cap, arbitrary allowlist, guessed resource capacity, or weaker required
protection. Explicit required user/admin limits must still be enforced at
their requested scope; fail only affected execution if proof is missing,
preserve existing prerequisite and L1 failure semantics.

The following P1-P6 are mandatory subfamilies of existing R2/R3/R5/R8/R10
and A6/A8/A10/A12/A13, not a replacement for R1-R10 or a separate milestone.
Apply every row at implementation, readiness, release and expansion of
affected capabilities. Map exact test IDs, native proof, owner and recheck
trigger in the existing acceptance/capture matrices; non-applicability
requires a concrete execution-scope rationale, not mere API absence.

| ID | Required proof and outcome |
| --- | --- |
| P1 | New/untested version or architecture with equivalent verified capability: normal execution, exact result, unchanged status/exit; no warning solely for a version label. |
| P2 | Optional API missing/changed/denied/malformed, partial OS/job/container/warehouse evidence, unknown version: retain valid independent facts; continue when required protection is independently proven; explain limitation and impact. |
| P3 | Required native control unavailable or ineffective: use an independently verified equivalent at the same required scope with explicit advice, or refuse only affected execution before unsafe data work; native resource failure is ERROR, not mismatch; no silent downgrade. |
| P4 | Warnings/refusals explain unavailable dimension, practical consequence, continue/refuse decision, and safe actionable recovery/override (only actually supported choices). Deliver through normal terminal diagnostics including successful checks and captured stdout/stderr orchestration logs; bounded deduplication per relevant scope/cause, no raw SQL, paths, values, environment contents, native exceptions or sensitive identifiers. M8.3 structured publication and later integrations preserve meaning and privacy. |
| P5 | Representative older and newer supported platform/engine/dependency combinations, constrained and capable environments, version/architecture-specific controls and actual effects. Record actual OS build/release, architecture, Python, engine/dependency versions, image label and outcome; a moving latest label is not a second distinct version or a certification claim. Include unknown/future/API-change fault injection, not only real images. |
| P6 | Maintain automated compatibility coverage and triage: pinned representative baseline and rolling recent images/dependencies, periodic and release/change-triggered validation, retain existing supported regressions, capture discovered failures with exact reproducer, affected scope and next required gate. CI unavailability is an explicit coverage gap, not proof or a runtime block. |

### Ownership and recheck checkpoints

| Owner/checkpoint | Mandatory platform obligation |
| --- | --- |
| M8.1.2 | P1-P6 for local DuckDB resource discovery, native controls, worker/IPC, scratch and warning behavior; implement and verify initial persistent multi-version compatibility CI before exit. |
| M8.2 / M8.3 | Preserve limitations and advice through invocation lifecycle, bounded diagnostic deduplication, cancellation and safe structured publication; no status/exit reclassification. |
| M10 / M10.7 / M10.8 | Readiness review of tested versus untested environments, user setup and warning/recovery guidance, reprove local scope expansion and platform matrix. |
| M11-M12 PostgreSQL | P1-P6 before experimental admission: actual client OS/driver/server/deployment, session/permission and native resource controls, transfer and cancellation as applicable. |
| M12-M13 Snowflake | P1-P6 before experimental admission: client OS/connector and warehouse/role/service capabilities, observed versus controlled resource and billing scope, no client RAM claim about warehouse capacity. |
| M13.5 / M18 | Re-evaluate client/remote/cross-context and authored-query scopes, resource controls and warnings on changed deployment or operation. |
| M29 | Shared reusable P1-P6 capability and graceful-degradation conformance; candidate-specific native environment/version matrix before official promotion or expansion; no forced common OS mechanisms. |
| M29 onward / any future candidate | Repeat before adapter creation/admission, promotion, version/deployment/operation expansion and relevant dependency/platform change. Distributed engines (e.g. Spark if later admitted) separately prove driver/executor/cluster scope. No new adapter or milestone is authorized. |
| M32/M32.1 and future integrations | Preserve safe actionable warnings in captured logs/events, correct statuses and privacy, including successful runs; no assumption that every orchestrator captures every stream. |

### Maintenance and CI policy

The [testing plan](../implementation/testing-plan.md#platform-and-dependency-compatibility)
owns the CI strategy; the [compatibility matrix](../compatibility/compatibility-matrix.md)
owns evidence and support claims. The initial local matrix must test distinct
representative currently supported OS releases per applicable OS family where
available, Python supported versions and relevant native engine/dependency
versions; justify a risk-based selection rather than an exhaustive Cartesian
product. Include older/current pinned OS images and a rolling latest lane;
verify actual distinct releases/builds, record gaps for unavailable images
or architectures and use authorized equivalent environments where needed.
Keep version-specific failures actionable and visible. Schedule periodic
compatibility runs and trigger reevaluation on dependency/OS/runner changes,
native-control changes, release/promotion and compatibility reports; maintain
a working manual/on-demand path. A scheduled workflow is not proof of its
own operation; inspect latest result, missed/disabled jobs and matrix
retirements at each relevant release/phase exit. Do not declare unknown
platforms certified or automatically refuse their safe use. Never freeze
runtime policy to CI runner resources or require the same tests/mechanisms
for a remote adapter where the scope differs.


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
Implementation authorized; no gate closed or exit approval granted.
