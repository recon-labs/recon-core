# ADR 0026: Local Execution Policy And Scan Admission

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

See the [approved M8.1.2 prework](../planning/milestone-8-1-2-prework.md) for the exact configuration, candidate/capture disposition and ordered implementation proof.

Status: Whole adaptive resource design reopened; implementation suspended
(2026-11-27). The previous accepted mechanism choices are historical pending
replacement design and approval. Current runtime unchanged. The approved amendment
below and [dedicated resource prework](../planning/milestone-8-1-2-prework.md)
supersede the historical footprint-driven resource decision, not the
verified read-only binding and L1 lifecycle requirements. No gate satisfaction
or implementation claim is made.

## Reopened design direction (2026-11-27)

The maintainer approved reconsidering the complete implementation, including
process placement, resource observations, calibration, transport and scratch
recovery. Favor native controls and maintained interfaces; require concrete
benefit and necessity for extra OS-specific mechanisms. Shared execution
resources are not inherently unsafe. Preserve actual noninterference with
unrelated sessions, required binding, exact outcomes, bounded results,
private scratch and no unrelated deletion, explicit supported controls,
truthful cancellation and cleanup. Optional missing observations are advisory
where otherwise safe. No automatic OS-version refusal or arbitrary workload
cap. Compare direct owned execution and conditional child isolation; do not
assume either is suitable before native proof. Automatic crash recovery is a
proposed scope reduction, not yet approved for removal. See the
[reopened prework](../planning/milestone-8-1-2-prework.md#current-status-whole-design-reopened-2026-11-27)
for comparative proof, outcome dispositions and approval blockers. All prior
mechanism-specific choices below are historical, not implementation authority.

## Consolidated replacement proposal (approval pending)

The [consolidated native-first replacement design](../planning/milestone-8-1-2-prework.md#consolidated-native-first-replacement-design-proposed-for-approval-2026-11-27)
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

See [current M8.1.2 configuration proposal](../planning/milestone-8-1-2-prework.md#exact-proposed-policy-and-configuration) for exact schema, ownership and acceptance variants. No prior released config migration.

## Proposed replacement following comparative proof (approval pending)

Maintainer scope decision (2026-11-27): M8.1.2 owns adaptive resource
management for both standalone and embedded Python usage. No deferral of
embedded adaptation or replacement admission to M8.2. Preserve shared
application safety and current API capabilities; prove the smallest native-first
mechanism without automatically restoring per-check workers, custom IPC or
OS ownership inspection. M8.2 retains full invocation lifecycle and cumulative
resource responsibilities. Exact mechanism and remaining scope dispositions
are not approved yet.

Ordinary configured native read-only sessions in a dedicated invocation passed
all nine check families on eight environment combinations; same-file external
readers unchanged, writers refused, database unchanged and scratch cleaned.
Independent in-process ATTACH is rejected as-is due to writer/catalog
regressions. Prefer the ordinary invocation, not per-check subprocesses or
custom IPC, and standard unique private scratch, not persistent recovery.
Native tuning remains valuable: untreated defaults OOM or fail binding on
real wider workloads; measured controls and separate scratch succeed.
See the [native-first redesign proposal](../planning/milestone-8-1-2-prework.md#native-first-redesign-proposal-2026-11-27-approval-pending)
for evidence, embedded API boundary, proposed reserve/recovery/worker scope
changes, gate and regression dispositions, and remaining proof. No new
architecture, default or implementation approved by this proposal alone.

## Historical accepted adaptive resource amendment (reopened)

Core owns the normalized project-local policy, admission, reason and advice.
The adapter owns actual native settings, evidence, placement, binding and
control effects. Default project admission has no database-size, row-count
or workload-time ceiling. Physical footprint is independent of work, memory,
temporary disk and returned/transported bytes. An explicitly authored
footprint maximum applies to all already supported local project checks,
including row count; unknown optional estimates do not refuse independently
proven scope/protection.

The optional `execution.scan-budget.local` project configuration accepts
positive strict integers `max-database-mib`, `warn-estimated-input-rows`,
`managed-memory-mib`, `threads`, `spill-mib`, `memory-reserve-mib`,
`disk-reserve-mib`, and an optional `scratch-directory` string. MiB is
1048576 bytes. Strict validation, checked native ranges, absent/empty
mapping semantics, maximum and reserve precedence, and path handling are
specified in the prework. No profile/CLI/environment/contract override or
user-authored classification. Explicit engine-managed ceilings are not hard
RSS, physical disk or CPU guarantees; no silent downgrade of a required
control. Reject malformed settings before native work.

Calculate effective headroom using independent available host and applicable
container/controller evidence, finite ancestor headroom and actual CPU and
scratch constraints, preserving provenance and unknown versus zero.
Use native engine recommendations only within independently observed
resource constraints. Initial DuckDB tuning candidate: reserve ceil(H/4)
of effective available memory H unless authored, cap requested/native
managed target at remaining headroom, and cap native/requested thread target
at ceil(effective CPU capacity). Initial disk reserve candidate ceil(F/10)
for actual free space F unless authored; spill target bounded by remaining
scratch capacity and native/explicit ceiling. Account for memory-backed
scratch separately. These are adjustable adapter-local tuning heuristics
approved for validation, not universal or locked numerical defaults;
validate final combination, capable/constrained workloads and pressure
before exit. No arbitrary minimum rounded upward, hidden retry or scope
mutation.

Use one isolated owned subprocess per admitted local DuckDB project check,
with verified read-only transaction and exact binding, a matched private
policy/lease, bounded ordered IPC preserving exact numeric domains, and
no arbitrary external SQL. Retain existing engine, renderers and comparison
semantics. Apply native resource controls before data work, explicitly set
spill limit after connecting and verify readback and native effects; startup
readback alone is insufficient. Observe actual pressure and distinguish
managed limits, process use, filesystem use and physical quotas. Portable
monitoring and parent-loss watchdog are best-effort, not hard containment.
Never claim hard guarantees without independent scope-specific enforcement.

Confirm worker exit before cleanup. Use private owned scratch with
coordinated parent/worker leases and verified local ownership; later recover
only proven inactive directories, never based on PID or age alone. If
cleanup or termination is uncertain, preserve L1 and stop further affected
execution. No immediate cleanup promise after parent crash. Actual resource,
worker, protocol and cleanup failure is ERROR, not mismatch; pre-query
required scope/control refusal is not_executable. Safe advisory diagnostics
on success/failure do not change reconciliation status or exit meaning.
No generated run-result/evidence/state/sink output or new public adapter
interface. Preserve existing prepared low-level helper behavior.

The dedicated prework assigns exact outcome codes, test families,
responsibilities, B8-B10 one-worker prerequisite lifecycle and exit proof.
Remaining invocation lifecycle and cumulative resource scheduling stay
with the subsequent run-lifecycle phase; durable safe resource evidence
with publication. Future adapter/version/placement admission and promotion
must independently prove applicable resource controls and evidence;
no requirement to reproduce DuckDB mechanisms on remote/distributed engines.

## Platform compatibility and graceful degradation

Untested versions are not runtime allowlists or blockers. Admission depends
on actual execution-scope capability and independently verified required
protection. Optional unavailable, unsupported or malformed observations
produce actionable safe advice and do not prevent otherwise safe work.
Verified equivalent mechanisms may be used at the same scope without
changing reconciliation meaning; required protection that cannot be
established refuses only affected execution. Native failures are errors,
not mismatches. Diagnostics explain what is unknown, practical impact,
whether work continues, and supported remediation, with bounded
deduplication and no sensitive values. Deliver through ordinary terminal
diagnostics, including successful checks, so orchestration capture can
retain them. No promise that every orchestrator captures every stream.
The [mandatory platform subfamilies P1-P6](../planning/execution-resource-safety-assignments.md#mandatory-platform-compatibility-and-graceful-degradation-gate-4l)
govern current and future adapter/version/deployment conformance, actual
native evidence, periodic compatibility validation and regression carryover.
Tested compatibility is distinct from untested best-effort execution;
no automatic version-based refusal, silent downgrade or universal OS
mechanism.

## Historical decision (superseded for resource policy)

The following baseline records earlier approved/reopened decisions for
traceability. Its footprint default, optional two-field-only syntax and
pending-design wording are not implementation authority. Existing binding,
scope, privacy and comparison safety obligations remain in force.

## Context

The existing local/dev scan guard bounds database file footprint and proves
local relation endpoints for certain checks. File footprint does not bound
decompressed bytes, logical rows, repeated scans, intermediate cardinality,
memory, time, or price. Catalog cardinality and optimizer estimates are not
guaranteed upper bounds, and count queries can scan data. A fixed-size returned
summary is a transport constraint, not scan safety.

## Decision

Use a project-owned execution policy, independent of contracts, profile
credentials, compilation and comparison semantics. Optional fields to implement in
recon_project.yml (config-version 1):

```yaml
execution:
  scan-budget:
    local:
      max-database-mib: 128
      warn-estimated-input-rows: 1000000
```

Both fields are positive strict integers (not booleans, floats, strings or
null), at most signed 64-bit maximum after conversion to bytes or rows.
One MiB is 1048576 bytes. Empty optional mappings are equivalent to absence;
unknown keys, duplicates and wrong types fail configuration validation.
Absent policy uses a conservative version-local internal footprint default
(initial implementation 64 MiB, chosen for compatibility, not a stable product
limit); the exact effective policy is recorded in memory. No default
estimated-input warning threshold is imposed: the optional authored threshold
is a soft warning, not an actual scanned-row ceiling. No CLI, environment,
profile, target, contract, package or authored status override is admitted.
Authored local footprint limit overrides the internal default only; it cannot
override missing or untrusted safety evidence. Future environment controls
require a separate precedence decision. The policy does not change check
definitions or compiled artifacts.

For the project-run boundary, admit only the already supported typed
relation-backed same-context local DuckDB base-table checks with known
project-local regular file footprint at or below the effective limit,
no retained WAL/tmp sidecar, unambiguous local catalog binding and a
supported execution/transport contract. Verify that proof belongs to the
actual executing connection and selected relations immediately before any
data query; a preliminary file/catalog probe alone is insufficient.
Validate resolved path and file identity before opening, after opening and
immediately before each data query, including sidecar and observed drift
checks. Use a dedicated owned read-only connection and transaction for
catalog proof and the authorized reads, without arbitrary SQL, temporary
objects, attachment or context mutation. Resolve each runtime relation to
its unambiguous verified catalog/schema/table identity and render that
qualified binding through the private runtime path; do not change the
public compile renderer or logical comparison. Read-only mode alone does
not prevent temporary name shadowing. Fail closed if binding or freshness
cannot be verified. This local/dev policy assumes a trusted project
filesystem and cooperative processes; it is not a sandbox or a guarantee
against hostile filesystem races. Do not create
a missing file, attach other catalogs, execute a data scan as preflight,
or rely on a user/adapter-provided final boolean. A typed plan, bounded
result envelope and local footprint restriction form a local/dev admission
policy, not a guarantee of actual workload or resource consumption.
No production execution claim or general-purpose hard physical scan-byte,
memory, runtime, billed-cost or total-run budget is made. If same-context
binding and non-executing scope evidence cannot be established with supported
versions, stop for design review rather than weakening the check.

Apply this policy to row-count, grain-key safety and supported explicit sum
checks, not just the previous scan-heavy subset. Row count is conservatively
classified as potentially scanning, unless a later explicitly proven
metadata-only execution strategy is admitted. Retain current exact row
count semantics for qualifying local base tables, including aliases and
explicit no-materialization. The approved compatibility restriction is
intentional: previously admitted row-count views, external/non-project
files, unbounded or missing scope no longer execute through project run;
an explicit larger local footprint limit can admit known local scope only.
No new support for in-memory databases. The exported prepared-adapter
execution helper remains a low-level pre-alpha primitive, not a
project-policy or safe-execution entry point. The actual project-run engine
route must not bypass admission; tests of injected collaborators must use
explicit trusted test evidence rather than production exemptions. Any need
to change public helper signatures or stable adapter-facing shapes reopens
compatibility review.

Supplement required local scope evidence with non-executing, catalog-bound
per-relation estimated cardinality as optional advisory information.
Distinguish absent/unknown, unsupported, malformed and available; never
interpret unavailable as zero. Count source and target input roles
separately even if they refer to one table; sum only comparable estimates
with checked arithmetic. The sum is estimated input rows for two endpoint
roles, not actual scanned rows, distinct rows, repeated operator scans or
join output. No human-format EXPLAIN parsing, executing plan modes, unsafe
storage-segment inspection, or exact table count scans for preflight. If
catalog estimates are available and exceed an explicitly configured warning
threshold, issue a nonblocking warning only if the hard policy admits the
check. Optional estimation failure must not fabricate advice or invalidate
otherwise proven admission; it must not conceal failure of required scope
proof. Use approved typed operations to describe bounded result envelope
and local transport separately; unsupported cost, actual scan bytes,
memory, timeout and intermediate estimates remain unavailable. A bounded
transport contract must be enforced independently, never by truncating
the logical comparison. No production estimate or transfer limit promises.

Core computes the final allowed/blocked status and reason. Hard footprint
excess uses existing scan_budget_exceeded taxonomy; missing/untrusted
required scope uses existing bounded_local_scan_required or scan estimate
unknown/unsupported taxonomy as appropriate; unsafe executing preflight
uses unsafe_scan_preflight. Invalid project settings are configuration
errors, not comparison failures. Keep existing artifact, plan, placement,
prerequisite, capability and lifecycle diagnostic precedence; do not
mask specific failures with generic budget reasons. A hard block is
not_executable (or existing prerequisite blocked outcome) with no
comparison values, not a data mismatch. An advisory warning is a distinct
diagnostic, not a CheckStatus.WARN reconciliation result. Preserve check
status and exit mapping; emit safe warning code/message/hint on successful
run as well as failed runs, without general CLI summary redesign. New
diagnostic RC_RUNTIME_SCAN_ESTIMATED_INPUT_ROWS_WARNING; existing safe
diagnostics for blockers, with revised actionable hints. Use fixed safe
wording, no raw plans, relation names, paths, values, row counts, rendered
profiles or native errors in public advisory output by default.

Keep private typed in-memory scope evidence, effective policy/origin, units,
availability, source/target roles, result envelope, admission status/reason
and advisory codes. No stable serialization or new artifact fields. No
automatic SQL rewrite, filtering, sampling, index creation, fallback or
scope mutation. Advice may suggest reviewing a known local footprint limit
or reducing scope explicitly, with unavailable subset/window/sampling
features identified as future and coverage implications stated. Deeper
native plan advice and production conformance remain later work.

## Alternatives

A file-size-as-scan-byte promise is false; a universal planner-estimate
ceiling is not a reliable actual-work bound. Requiring every local user to
configure limits sacrifices onboarding. Allow-unestimated overrides defeat
admission. The scoped local policy and truthful advisory metadata preserve
a conservative local path without claiming stronger guarantees.

## Consequences

Additive project config syntax and intentional row-count admission
restriction have maintainer approval and require implementation tests,
compatibility and changelog updates and user migration guidance. No version-floor change
or public typed-operation/adapter interface or artifact-schema change is
authorized. No result/evidence/state/sink writing, query endpoints,
production adapters, selectors or sampling implementation. See phase
prework for exact readiness and conformance requirements.

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](../planning/execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is implemented and verified on main (PR #38). Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

Reopened binding direction: fresh owned read-only per check, per-check transaction, verified exact relation identity, no writable fallback. Uniform protected local base-table scope approved; keep legacy 64 MiB key/SUM guard only, do not add it to row count. Resource policy/defaults remain reopened. Exact private integration, diagnostic, path/identity and acceptance proof require separate detailed approval.

## M8.1.1 approved binding lifecycle amendment

See [M8.1.1 prework](../planning/milestone-8-1-1-prework.md). Maintainer approved L1 check-local native
failure isolation; configuration/setup precedence retained. Cleanup
uncertainty stops further native work without proven isolation. Final
check ERROR carries no comparison values; dependent checks use actual
prerequisite blockers. Existing status/reason/exit taxonomy and public
API signatures remain unchanged. Two additive Core runtime
diagnostics: RC_RUNTIME_BINDING_PROOF_FAILED and
RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE. Existing connection/query/close
codes retain safe messages. The approved binding is implemented and verified on main (PR #38), with
scoped exit approval complete; it is not a
new public stable capability. Resource settings and defaults remain reopened.

## Historical M8.1.2 resource policy handoff (superseded)

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

## Historical adaptive resource direction and adapter carryover (superseded)

Maintainer-approved adaptive, adapter-aware, minimally restrictive local execution with portable best-effort protection, strict controls only when proven and isolation where necessary. Preserve native spilling and larger-than-memory work. No universal CI-derived ratios or caps. Distinguish execution scope from client transport, use engine-specific mechanisms and never downgrade required enforcement. Apply [Gate 4L adapter-specific resource applicability and proof](../planning/execution-resource-safety-assignments.md#mandatory-adapter-specific-resource-applicability-and-proof) to all future adapters and expansions. Exact settings, defaults, worker design and pulled-forward lifecycle requirements remain pending detailed prework and separate approval. No successor implementation authorized.
