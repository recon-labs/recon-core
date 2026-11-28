# Milestone 8.3 - Run-result publication and CLI finalization

Status: Maintainer-approved detailed design direction (2026-11-28); implementation
not authorized. Synthetic cross-platform filesystem feasibility passed 9/9; cumulative
prework review and implementation approval remain required. Baseline M8.2 merged as
fdde61ca2ae5f4784ffe520f543ac24458d9574d (PR #44, 19/19 CI).
Split Decision: Already Split / Follow Existing Split. C1-C10 are one coherent
publication contract; no new repository, execution strategy or infrastructure.

## Scope and authority

Implement the first versioned local result snapshot and final terminal
summary, consuming the existing single invocation outcome. Follow
[ADR 0028](../decisions/adr-0028-run-result-publication-and-cli-finalization.md),
ADR 0021/0022/0025/0027, the [split assignment](milestone-8-split-assignment.md),
artifact versions and the milestone process. Do not serialize the internal
RunResult or Diagnostic dictionary wholesale.

Non-goals: new check types, selectors, implicit compile/freshness/cache,
result history, evidence rows, failure details, reports, state, table or remote
sinks, new settings or output flags, adapter API changes, automatic retry,
global execution lock, OS-specific production worker, arbitrary size cap.
Do not close future type/scope/adapter/evidence/integration gates.

## Execution and publication ordering

RunService.execute and CLI share one execution and one required local
publication. Preserve keyword-only controls and ServiceResult's four fields.
Keep the private execution-only seam for existing execution/no-write tests.
Capture destination at the existing successful project-context load, not
by loading again. Before compiled/native work, validate the reserved target
and invalidate its previous regular snapshot. A stop observed after trusted
context acquisition does not bypass destination preflight; after successful
preflight it is eligible for a stopped artifact without native work. Failed
preflight is runtime exit 3, no native work. Invalid CLI arguments create
no invocation; invalid embedded controls, preset cancellation or configuration failure before a
trusted destination exists cannot publish or invalidate guessed paths.
Explicitly report no current result written. After destination preflight,
early compiled, configuration, runtime and stop outcomes are eligible for a
truthful failure artifact. Never present an incomplete or foreign engine
result as a verified check outcome. Known empty differs from unavailable.
Use existing aggregation/exit authority; preserve earlier independent
configuration/validation failure and all distinct safe diagnostics.

Execution start/finish/elapsed retain the M8.2 meaning through native cleanup
and final seal, including destination preflight. Publication follows the
seal; it cannot retrospectively change comparison results or stop cause.
The command waits for publication. Neither deadline nor atomic replacement
implies a hard wall-clock or power-loss guarantee.

## Snapshot lifecycle

Use configured target-path (including otherwise supported absolute paths).
The reserved filename is run_results.json. Reuse appropriate path helpers;
verify real directory, reserved regular single-link file, no redirects,
symlink/junction/reparse redirects, case-insensitive collisions, special
files or directory/file shape mismatch. Verify directory/file identity at
ownership boundaries; fail closed on required identity uncertainty. Do not
broaden the trusted/cooperative filesystem boundary into a hostile concurrent
mutation guarantee. Create directories only under the validated configured
destination. Remove only the old reserved regular snapshot at preflight,
including malformed old JSON; never follow or remove a link, directory or
unrelated output. Failure to invalidate blocks execution and explicitly
reports possible stale output. No cleanup of compiled/evidence/state files.

Stage strict UTF-8 JSON (allow_nan=False) using exclusive unique temporary
sibling creation; validate the complete projection, stream JSON to the owned
file, flush and close before same-directory atomic replace. Recheck safe
destination and ownership before commit. No fallback copy, retry, arbitrary
output size limit, or required post-commit operation that could turn a
committed snapshot into a purported failed publication. Cleanup only owned
temporary file after verified identity; report retained/uncertain residue
when cleanup fails. Never sweep unknown abandoned staging files. No promise
of power-loss durability. Abrupt exit before commit can leave an owned
temporary file but cannot publish partial final JSON.

Same-target overlap is allowed without global serialization. Define ordering
by the actual filesystem operations, not invocation start or the first stat:
preflight invalidation is the successful unlink of the reserved regular
snapshot (or observed absence); publication is successful atomic replacement.
A later invalidation can legitimately remove a prior successful publication,
even if its preflight began earlier. If a different identity is observed
before unlink, fail preflight safely rather than retrying or deleting that
observed replacement. Concurrent disappearance of the reserved name is
acceptable only with the destination still verified. Portable stat/unlink
is not an atomic compare-and-delete; a replacement in the final check/unlink
window is governed by operation ordering within the cooperative boundary,
not a guarantee of preserving the initially inspected inode. Never claim
stronger conditional deletion or hostile-mutation safety. After preflight,
failed staging/publication cleanup must never unlink the final name or
another invocation's staging file. Separate targets are needed if each run
must retain its snapshot. Correlate invocation_id with command output; a
written result means this invocation committed, not that its file necessarily
still exists when the command returns. No historical store, shared lock or
new directory policy. Concurrent mutation of compiled inputs is not a
freshness guarantee.

## Version 1 schema

All listed keys are required; null means unavailable/not applicable as
specified, empty list means known empty. Integers are exact nonnegative
counts unless otherwise stated; booleans are not numeric counts. No NaN,
Infinity, raw object payload or general extras. Readers reject an unknown
version for interpretation and can ignore additive unknown fields of a
compatible version. Removing, renaming or changing meaning/type requires
compatibility review and version bump where breaking. Manifest and compiled
artifact versions unchanged.

| Top-level key | Type / meaning |
| --- | --- |
| artifact_type | fixed string run_results |
| artifact_version | integer 1 |
| recon_version | version string |
| generated_at | UTC preparation timestamp, not disk commit timestamp |
| invocation_id | existing M8.2 run ID |
| invocation | lifecycle object below |
| project_name | canonical authored project identifier or null |
| scope | scope object below |
| reconciliation_status | existing RunStatus or null |
| summary | seven check-record counts or null |
| contract_results | ordered contract records or null |
| diagnostics | ordered safe diagnostic records |
| execution | invocation execution evidence below |
| publication | local required/written object below |
| artifact_refs | one committed local self-reference |
| sink_refs | empty list, no configured external sink |

Invocation: started_at, finished_at (UTC), elapsed_ns (monotonic integer),
stage (project_configuration, compiled_checks, compiled_contracts,
runtime_setup, check_execution, result_projection, or
result_publication_preflight), status (completed/failed), stop_cause
(run_cancelled/run_deadline_exceeded/null), timeout_seconds (positive integer
or null), exit_category and exit_code (existing service mapping, execution
primary; equal to final command if published). No fabricated stop confirmation.

Scope: kind whole_compiled/unknown, planned_contract_count,
planned_check_count, finalized_check_count, executed_check_count
(integer/null), complete (boolean/null), selection (null, no selectors).
Complete means verified result record coverage, not all checks compared or
data equivalent. Known empty has zero checks and no_checks only when
authoritative; do not infer contract count or complete coverage. Early
failure with no plan or result uses unavailable scope/counts except actual
known facts. For inconsistent/foreign results retain trustworthy plan facts,
complete=false, suppress untrusted record counts/status/results. Summary
keys pass, fail, warn, error, skipped, blocked, not_executable count check
records only; sum matches trustworthy finalized count. Null when unavailable,
zero when proven empty. No authored freshness claim.

Contract records: contract_ref (positive invocation-local plan ordinal),
contract_id and contract_name (each canonical authored identity or null), status
(existing RunStatus), check_results (ordered list), diagnostics (safe list).
Check records: check_ref (positive invocation-wide plan ordinal), check_id
and name (each canonical authored identity or null), check_type (known
catalog type or null), status (existing CheckStatus), severity (validated
error/warn/info),
executed (boolean), reason_code (existing CheckReason or null),
prerequisite_refs, blocked_by_refs (positive plan ordinals), and
missing_prerequisite_count (integer for unresolved references), diagnostics
(safe list), execution (object), artifact_refs=[], sink_refs=[].
Use actual validated plan order and existing stable ID conventions. Validate
canonical ID composition and names at projection against the existing
compiler/config naming authority, not a new naming rule. Retain the check
name from the validated loaded plan at its existing owner; never use the
engine's name or identity as public identity authority. Plan membership alone
is not proof of canonical naming; arbitrary injected/loaded strings, even
matching the result, must pass the canonical checks. An identifier is public
metadata only in its allowed authored field, not a license to publish it in
arbitrary diagnostics. Suppress noncanonical strings but preserve ordinals
and outcomes, not a new execution admission restriction. Resolve prerequisite
and blocked-by refs only to verified plan identities; unresolved prerequisite
count is structural and no unknown identifier is echoed. Do not invent absent
links. No new parse/compile or freshness check.

Publication object: mode=local_artifacts, required=true, status=written,
artifact_type=run_results, path=run_results.json (relative to configured
target). artifact_refs contains the matching artifact_type/path pair. This
object is observable only in the successfully committed snapshot; on write
failure the service/CLI reports failed or not written, never a reference to
the current result. No reference to unproduced SQL/evidence/state/sink outputs.

## Privacy and diagnostics

Allow only canonical authored identifiers (public metadata; users must not
put secrets in them), approved categorical facts, structural record counts,
configured control limits, verified typed settings evidence and safe
diagnostics. Suppress source/target row counts and values, raw or normalized
keys, aggregate values, differences, failure counts, raw tolerance/null/
normalization payloads, relation and connection identifiers, arbitrary
operation/capability names, SQL/plans, native exception text, profile/DSN/
environment/host data, filesystem paths and arbitrary refs. Do not infer
values or policy application from the result shape. Gate 4O is not applicable
because no approximate or derived comparison values are exposed.

Diagnostic record: code (known Recon code or
RC_RUNTIME_DIAGNOSTIC_UNAVAILABLE), severity info/warning/error, nonempty
safe owner-authored message, resource_type known safe category or null,
resource_name canonical safe identity or null, path approved fixed relative
reference or null, line/column positive integer or null when safe, hint safe
action or null. Context via nesting and safe ordinal attribution. Audit
run-path producers, correct unsafe interpolation at its owner, preserve
actionable diagnostics and distinct failure events. A known code, prefix,
valid severity, or Diagnostic type is not provenance. Establish safe text
at the existing producer/boundary through fixed owner-authored templates
and explicitly validated typed arguments; audit project/config/profile,
compiled loaders (including stored diagnostics), adapter setup, check engine,
native runner, stop/cleanup and publication owners. Do not promote persisted
or injected diagnostic text, hints or context to trusted text merely because
its code matches a real one. Use a fixed safe fallback and inspect-locally
action for unproven text/fields, retain a known safe code only when its meaning
is trustworthy, otherwise use RC_RUNTIME_DIAGNOSTIC_UNAVAILABLE. Preserve
separate failure events via safe plan/session ordinal attribution even when
fallback text is identical; deduplicate only proven repeated events, not
all equal sanitized strings. Do not duplicate the catalog or implement a
regex-based privacy claim. One safe projection for artifact, service and
terminal, including service message and successful-run diagnostics; preserve
existing non-run CLI rendering.
Existing parse/compile writer exception text is an independent privacy
carryover to next affected writer/compatibility review, not a global rewrite.
C3 tests use unique canaries in every potentially unsafe field, including
nested/injected results and diagnostics; assert absent on all public surfaces.

## Execution and resource evidence (C2/C10)

Invocation execution object: attempted_check_count, native_execute_attempts,
native_fetch_attempts, peak_active_native_checks (integer/null);
actual_scanned_rows, actual_cpu_ns, actual_disk_bytes,
actual_transport_bytes, actual_cost (null in v1, unmeasured);
actual_resource_evidence=unavailable; physical_enforcement_proven=false.
Native comparison-reader counts exclude setup/metadata/close; attempts are
not completed checks or scans. If attempted work lacks accounting proof,
do not sum missing native records into an invented zero. The existing ledger
counts attempts at session entry, before open/bind, not only successful
queries. Retain per-check attempt and final cleanup facts at the bound runner
and actual native interrupt/return and scratch facts at their owners. Prove
coverage for each attempted check; if any applicable native count is missing
or untrusted, the affected cumulative count is null, not a partial sum.
Zero is allowed only for observed zero or a proven no-attempt path. Do not
infer release, scratch deletion, interrupt delivery or returned calls from
status or diagnostic presence/absence. Invalid or absent controls and an
unavailable plan must not manufacture timeout or execution facts.

Per-check execution object: adapter_type (known duckdb/null), placement
(same_context only on verified binding/null), required_capabilities (known
catalog names list/null), unknown_required_capability_count (integer/null),
capability_admitted, preliminary_allowed (boolean/null), preliminary_reason
(CheckReason/null), admission (not_reached/refused/unverified/verified/null),
attempted, native_released, scratch_release (boolean/null), cleanup_status
(not_started/completed/failed/unconfirmed/null), native_execute_attempts,
native_fetch_attempts (integer/null), native_controls (object/null).
Additional fields native_interrupt_requested and native_calls_returned
(boolean/null) record actual interrupt request delivery to the native call
boundary and confirmed return of owned executing/borrowed interrupt calls,
respectively. Neither proves the interrupt caused termination. Null means
unavailable/not applicable; no inferred confirmation from a stop cause.
Retain at actual owners; null absent proof. Release may be confirmed despite
rollback failure; failed cleanup is not necessarily an unreleased handle.
No diagnostic parsing, native re-query or repeated engine evaluation.

Native controls is available when either policy or native evidence exists;
missing observation fields remain null. Its source_policy and target_policy
are arrays/null, each setting
fact has setting (managed-memory/threads/spill/max-database-mib/
warn-estimated-input-rows/scratch-directory), scope
(default/project/target/connection), mode (auto/none/fixed/percent/path),
requested_value (integer/null), unit (bytes/threads/rows/percent/null).
Use percent for percent mode; for fixed mode managed-memory, spill and
max-database-mib are normalized bytes, threads are threads, and the advisory
threshold is rows. Auto/none/path modes have null requested_value and unit;
scratch path never emitted. For each of memory, threads, spill retain
requested, adjusted, assignment, reported_lower, reported_upper
(integer/null), plus unit (bytes or threads); each control object is null
when its observation is unavailable. Capacities only
memory_capacity_known, cpu_capacity_known, spill_capacity_known
(boolean/null); estimate not_requested/unknown/within_advisory/
exceeds_advisory/null; readback_verified boolean/null;
physical_enforcement_proven=false; advisory_codes list of known safe codes
or null if unavailable.
Threshold rows are configured limits, not measured rows. No actual host
capacity, estimate number, raw path, physical use or guarantee. Policy
evidence and observed controls never replace actual resource consumption.

R1-R5: preserve independent dimensions, availability, actual binding,
existing policies and native readback; no new execution policy. R6-R8:
preserve deadline/cleanup, owner evidence and independent runs; safe write,
stale and residue semantics. R9: existing advice only, no optimizer.
R10: no new adaptive workload strategy; retain A/B and platform proof.
Future native adapters and resource/evidence expansions retain gates.

## Exit and terminal contract

Keep existing status precedence and exit codes (0 pass/warn/skipped,
1 mismatch, 2 validation/usage, 3 runtime/no_checks/blocked/not_executable,
4 configuration). A mandatory publication failure changes previous 0/1/3 to
3, preserves independent earlier 2/4, appends safe write and cleanup
diagnostics without erasing primary reconciliation outcome. Failed preflight
blocks native work. No successful exit for required write failure. Terminal
reports invocation ID, trustworthy planned/finalized/executed/attempted
counts, all check statuses and primary outcome, actual published/not-written
status and actionable safe diagnostics. Unknown counts not zero. Keep the
four-field ServiceResult contract: the safe run-specific message carries the
summary and current publication outcome; no added public result fields or
second CLI status authority. Distinguish the sealed execution status and
primary category from final command category on publication failure; a
committed snapshot has the same category/code as the returned command.
When a snapshot commits, ID/status/counts and final exit agree. A failed
publication cannot be represented as written merely by finding an older or concurrent
snapshot. Keep existing SIGINT and late-seal semantics.

## Acceptance and conformance matrix

| ID | Required positive, negative and edge variants | Proof / ownership |
| --- | --- | --- |
| C1 | Strict v1 shape/order/IDs/nullability; pass/fail/error/no_checks; canonical/noncanonical IDs and matching injected strings; differing engine name; configured external target; unknown future version and additive fields | Golden schema and service projection, artifact versions, no compiled version change |
| C2 | All nine native check families; actual verified and refused binding; unknown/missing capability; aliases; absent facts | Native owner trace and projected categorical metadata, no fabricated placement |
| C3 | Canary every sensitive field, nested payload, known-code spoofing, persisted/injected diagnostics and service messages, malformed IDs, raw errors/paths/SQL/profile values, safe distinct actionable warnings and equal-sanitized distinct events | Public service/CLI/artifact privacy and diagnostic owner tests; Gates 3F2/6/4J |
| C4 | All check/run statuses and mixed precedence, early/empty/invalid/foreign scope, setup failure, pre-start/active/late stop, cleanup and write failure combinations | Service and actual native tests; existing aggregation and primary mapping |
| C5 | Stale regular/malformed snapshot; missing target, wrong shape, symlink/dangling link/junction/hardlink/case collision, external target; permission/disk/close/replace/cleanup failure, abrupt exit, overlapping preflight/replace (both orderings, observed replacement, disappearance and final stat/unlink window), failed writer cleanup after another commit, unrelated files | Dedicated writer and real Linux/macOS/Windows filesystem tests; no native work on failed preflight; no partial final JSON, unrelated deletion or post-preflight deletion of another run's output |
| C6 | All status/counts, exit 0-4, actual write/not-written, unknown vs zero, safe warnings, matching artifact; delivered/ignored SIGINT and sealed outcome | CLI/service end-to-end and native regression, no extra execution |
| C7 | Only reserved local snapshot and owned staging touched; no other refs, report/evidence/state/sink/table/external writes | Filesystem and adapter trace, ADR 0022 |
| C8 | Whole compiled plan vs unknown/empty/incomplete coverage; no selectors/implicit compile/freshness claim | Scope tests and selector-readiness |
| C10 | Policy origins/resets/units, native readback, unknown actual resource use, exact attempts vs records (open/bind failure, absent native fact, partial count, observed zero), release/cleanup and stop evidence (failed rollback with confirmed release, unconfirmed close, interrupt request vs return), independent concurrent invocations | Owner-native facts plus projection, R1-R10 and existing A/B proofs |
| C9 | All C rows plus A/B regression preservation, compatibility, changelog, docs, exact final CI and cumulative review-fix | Full standard/platform CI, regression capture advisory and pre-commit |

Workflow scenarios: a mixed pass/fail invocation publishes once with exit 1;
a prior pass followed by invalid compiled input invalidates old result and
publishes current error; unknown destination leaves no current artifact and
does not guess cleanup; invalid output path blocks native work; deadline
preserves finalized checks and explicit unstarted reasons; disk-full after
mismatch preserves mismatch while command fails 3; independent validation
retains 2 on write failure; failed post-preflight publication cleanup preserves
another successful commit, whereas later preflight invalidation may remove it;
abrupt stage exit leaves no partial final
file; hostile strings never leak through service, CLI or JSON.

## Source and responsibility map

| Owner | Allowed responsibility | Forbidden / boundary proof |
| --- | --- | --- |
| services/run.py, services/_run_lifecycle.py | Once-only invocation, destination preflight handoff, sealed outcome and publication result | No JSON policy duplication, reload, rerun or raw output; service seam tests |
| check_engine/models.py | Existing aggregation and statuses | No file I/O or new status precedence; preservation tests |
| services/_bound_runner.py, adapters/_project_binding.py, adapters/duckdb/_bound_execution.py | Actual typed native facts/cleanup/call accounting | No writer, re-observation or BaseAdapter public expansion; native trace |
| Private service result projection module | Pure allowlisted typed public shape and safe diagnostics | No native/FS work or generic model dump; schema/privacy tests |
| artifacts/run_result_writer.py and reusable artifacts/_paths.py | Safe reserved-path preflight and atomic stage/commit/owned cleanup | No engine/status policy, unrelated deletion, scheduler or generic writer registry; real filesystem tests |
| cli/main.py, services/results.py | Render service-derived summary and existing exit mapping | No writer/adapter orchestration or second status authority; CLI tests |

Potential test modules: tests/artifacts/test_run_result_writer.py,
tests/services/test_run_result_publication.py and projection tests, existing
CLI and actual native suites. Update existing capture rows and route new
modules/tests to owning run_results, artifact, diagnostics and CLI surfaces.
Existing negative no-output tests remain true for the execution-only seam;
public run tests change only the deliberately added publication behavior.
Do not weaken preservation assertions to reach green. Re-evaluate all matching
capture rows via the index, including compiled-artifact-yaml-loader-diagnostics,
aggregate-service-output-privacy, local-resource-config-strict-validation,
compile-command-terminal-contract and run timeout/cancellation carryover, plus
all native/engine/privacy rows assigned in the split matrix. New writer,
projection and service paths require exact capture routing; retain existing
markers and test intent, update deferred rows only on verified proof, and
add reusable missed-requirement rows for privacy, accounting and publication
regressions. No gate closure from docs-only work.

## Steps, gates and Definition of Done

Research decision: completed (targeted local publication primitives).
The resulting constraints are incorporated in the snapshot lifecycle and C5;
production path, ownership, failure and platform conformance remains mandatory.
No generalized research or new infrastructure is needed for locked scope.

1. Audit approved C1-C10, Gate 5/5E/3F2/6/4J/4L/4I, selector readiness and
   current owners; verify M8.2 baseline and no orphan. Done for direction.
2. Lock ADR, schema/privacy/precedence/lifecycle contract and acceptance
   matrix. Targeted atomicity research converted to portable primitive
   constraints; platform feasibility required before lock. Review-fix ongoing.
3. Synthetic feasibility passed 9/9 maintained OS/Python lanes in isolated
   CI: exclusive sibling stage, replacement, deterministic overlap and failed
   temp-only cleanup, abrupt precommit exit, directory refusal, hardlink and
   symlink/junction detection, stable directory identity. This proves the
   primitives in those environments, not the production writer, all path
   guards, reader-sharing behavior, crash durability or all filesystems.
   Require production conformance at C5 and C9.
4. Integrate public ADR, prework, architecture, artifact versions, inventory,
   compatibility matrix, testing/build order, user docs and README status.
   Planned behavior distinguished from implemented behavior; validate links
   and drift. Obtain separate implementation approval before source changes.
5. Implement test-first C1/C3/C8 projection and owner diagnostics, then
   C5/C7 writer, then C4/C6 service/CLI handoff and C2/C10 typed evidence.
   Each dependent slice requires actual RED for critical privacy/lifecycle
   regressions, relevant GREEN, review-fix-revalidate and anti-pattern check.
6. C9 cumulative review against C1-C10 and A/B preservation. Full 10 standard
   and nine platform jobs, exact final head, branch-wide capture advisory,
   pre-commit, no missing capture decision or unsupported claims. Review-fix
   until clean; docs/compatibility/changelog and future assignments updated.
7. Present separate maintainer merge approval; no implicit release.

Gate dispositions: Gate 5 existing lifecycle reused, public result proof
pending; 5E writer lifecycle proof pending; 3F2/6/4J public diagnostics and
privacy proof pending; 4L/4I actual facts and resource uncertainty preserved,
C10 proof pending; 4O not applicable (no approximate/derived value output);
Gate 4P no type semantic expansion; selector readiness only, no subset
execution. Future M9, M9.5, M10.5/10.6/10.8, M11-M13/M13.5/M18, M29/M31/M32
retain assigned gates; no global closure. No new repository until the existing
M10.5-M10.7 checkpoint. New Unreleased entry on implementation, no migration
from a previous durable run schema. No public implementation claims until
actual tests pass. Local authenticated checkout unavailable; equivalent
GitHub API/CI fallback, disclose exclusions and residual platform limits.

Definition of Done: approved exact contract and feasibility, all rows proven,
no unsafe output or scope regression, no material owner/anti-pattern finding,
current README and public contracts, all required CI and capture evidence,
cumulative clean review and explicit merge approval.
