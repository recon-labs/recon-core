# Milestone 8.1.2 - Adaptive Local Resource Policy And Admission

## Current status: whole design reopened (2026-11-27)

**Implementation suspended by maintainer.** The previous detailed design and
implementation authorization below are historical, not coding authority.
Reopen the complete resource policy, execution placement, worker/transport,
resource observation, temporary storage and recovery design. No merge,
production activation, guard removal, or successor implementation before
revised detailed prework, evidence and separate approval. Preserve existing
candidate code, tests and historical evidence until explicit disposition.
Split Decision: Already Split / Follow Existing Split; reassess the B8-B10
prerequisite boundary with M8.2, not a new documentation-only milestone.

### Design audit and native-first direction

Resource safety is an outcome contract, not a mandate to reproduce OS
resource management. The current candidate is disproportionately coupled
to platform ACL, mount, identity, resource hierarchy and lifecycle internals.
Native test success does not establish the value or long-term compatibility
of each mechanism. The following is the approved redesign direction;
individual replacement mechanisms, defaults and scope changes remain
proposals requiring proof and detailed approval.

| Area | Priority and proposed disposition |
| --- | --- |
| Exact read-only binding, typed plans, exact comparison, bounded native results, privacy, no unrelated mutation | Essential; preserve M8.1.1 and M7.4 protections and existing public compatibility. |
| Default admission, optional footprint cap | Essential; remove arbitrary default footprint guard only after replacement proof. Explicit authored cap all nine families; no implicit sampling or data movement. |
| Native memory/thread/spill controls | Essential at the promised scope; prefer native defaults and explicit supported settings, compare measured adaptive tuning. Readback alone insufficient; no hard RSS/disk/CPU guarantee. |
| Host/container/CPU/disk observations | Beneficial, generally optional; use maintained portable/native interfaces and trustworthy available facts. No mandatory exhaustive hierarchy, external-process ownership or process enumeration; unknown is not zero or unlimited. |
| Reserve formulas and pressure polling | Reopen; justify incremental benefit over native defaults with real workloads. No locked 25%/10% default, arbitrary workload deadline, or universal resource monitoring subsystem. Known limits and actual failure remain distinct from advisory estimates. |
| Per-check subprocess, IPC, watchdog and placement proof | Conditional, not mandatory mechanisms. Compare existing owned connection with native controls/interrupt against a standard owned child when demonstrably necessary. Shared process/machine is not inherently unsafe. Never kill a shared process or alter unrelated connections; setting restoration alone does not prove noninterference during execution. If child selected, prove bounded exact transport, privacy, termination and cleanup; no duplicate executor. |
| Private temporary storage and normal cleanup | Essential; prefer unique secure standard-library directories under selected base and normal native close/cleanup. Targeted platform-specific protection only if necessary to meet actual privacy/ownership outcome. No implicit location switch. |
| Stable project namespace, persistent tickets, native ACL/mount allowlists, two-lease protocol, abandoned directory recovery | Reopen; proposed removal of mandatory automatic recovery. Prefer never adopting/sweeping old directories; leave uncertain residue for user/OS retention policy. If a particular additional mechanism is retained, justify it by concrete failure of simpler approaches. Preserve existing tests until explicit replacement/retirement approval. |
| Error, cancellation, diagnostics and L1 | Essential outcomes; distinguish requested from confirmed stop, native error from mismatch, current cleanup uncertainty from unrelated old residue. Warn about known material uncertainty, not OS version labels. Affected context only; do not promise discovery of unknown abandoned data. |
| Future compatibility | Essential P1-P6, all R1-R10 dispositions, risk-based older/current and rolling native lanes, actual OS/build/architecture/Python/engine evidence, failure injection and recheck. No mandatory OS-version allowlist or uniform engine mechanism. |

### Redesign preflight and exit blockers

1. Compare native-default direct execution, explicitly configured direct
   execution, and conditional standard subprocess isolation using actual
   bound Recon SQL and all four existing DuckDB pins. Demonstrate settings
   effects and simultaneous observer connection behavior, cancellation,
   errors, cleanup and exact results. If native global settings interfere,
   do not silently override unrelated sessions. Decide which settings/modes
   require isolation; no fallback/retry or termination of unowned process.
2. Compare useful native defaults against optional portable resource
   observations, explicit controls and measured tuning in constrained and
   capable environments, including large safe versus small costly workloads,
   changing shared load, unavailable metrics, full disk, and startup spill
   cap mismatch. Reassess each existing config leaf, default, scope,
   precedence and diagnostic; no new dependency or public syntax lock yet.
3. Prove simple per-execution scratch creation/normal cleanup and actual
   privacy on older/current representative platforms and supported Python;
   concurrent independent invocations, arbitrary existing paths, replacement,
   errors, abrupt exit and retained residue. Retain no-delete-unowned
   invariant. Automatic abandoned recovery is a proposed scope reduction,
   not yet an approved implementation removal. No blanket filesystem refusal
   solely because optional classification is missing.
4. Reconcile every A1-A13/R1-R10/B8-B10/P1-P6 variant, existing regression
   capture and gate assignment with the selected architecture. Keep
   regression outcomes; explicitly replace, retire or reassign only
   mechanism-specific cases with rationale, owner, equivalent proof where
   applicable, and maintainer approval. Record exact tested evidence, not
   fabricated test nodes. Preserve M8.2 remaining invocation lifecycle,
   M8.3 C10, M9.5 type and M10.8 scope restoration, M29 conformance and
   all future adapter responsibilities.
5. Present revised configuration, responsibility map, acceptance matrix,
   BDD, test plan, compatibility/diagnostic semantics, candidate code reuse
   or removal decisions, and DoD for separate approval. Only then authorize
   test-first implementation. No gate closure from this audit.

The prior prework below remains a historical baseline for disposition and
traceability, not a competing implementation plan.

## Native-first redesign proposal (2026-11-27; approval pending)

This section is a decision proposal based on comparative evidence, not
implementation authority. The suspension above remains controlling until
maintainer approves the scope/architecture, remaining targeted feasibility
and exact replacement test plan. No code or regression removal yet.

### Comparative evidence and recommended architecture

- Ordinary configured native read-only session in a dedicated CLI invocation:
  45917130110, all eight lanes passed, nine check families twice per lane,
  concurrent external reader unchanged and usable, external writer refusal
  before data query, successful fresh invocation after writer release, all
  native sessions released, fixture digest unchanged, normal scratch cleanup.
  Test-only factory injection and Click entry, not a released feature.
  Four DuckDB pins (1.0.0/1.3.2/1.4.5/2.0.1), Python 3.11/3.12/3.13,
  Ubuntu 24.04/rolling, macOS 15/26 ARM64, Windows Server 2022/2025 AMD64.
- 45914933298 and 45915029872: all four ordinary default connections
  execute exact bounded results and native interrupt leaves an observer
  usable. All four same-instance literal SET controls also affect another
  connection to the same file. Connection config may silently be ignored
  (1.0.0) or refuse (newer pins); separate invocation readbacks and observer
  comparisons succeeded. Do not set global controls on an unrelated shared
  instance, even if restoring later. No process enumeration to infer safety.
- 45915290150, 45915436600 and corrected 45915719518: narrow three-million
  groups in ~770 MiB file succeed at 512 MiB memory with default or configured
  settings; configured cases actually spill. Wide working set native default
  512 MiB all four kernel OOM; 2 GiB two OOM, two binding failures from
  database-adjacent spill sidecar. Configured 2 GiB case all four exact,
  disk spill and cleanup. Earlier observer race corrected; no size proxy
  or hard physical quota inferred. 1.0.0 native memory reports host-scale
  12.4 GiB in constrained environment. Native defaults alone insufficient.
- Independent in-process ATTACH candidate rejected as-is: 45915705053
  small exact success, but 45916233353 older-pin writer exclusion and
  valid catalog/filename regressions; 45916249562 all eight constrained
  cases fail initialization (cause not established). No alias/registry
  workaround, version exclusion or weakening existing binding.
- 45915266290 + 45915370906: eight effective standard-temp lanes across
  six OS releases, unique directory, concurrent creation, normal cleanup,
  abrupt-exit residue retained and new execution independent. Windows
  Python 3.11 inherited Everyone grant in synthetic shared parent,
  Python 3.13 protected directory on tested Windows builds. POSIX mode
  0700 is not complete ACL/ancestor proof. No different-user/native
  permission adversarial claim. Target privacy work only where needed.

**Preferred:** ordinary native read-only sessions and existing typed plan,
binding and comparison in the invocation process. A real dedicated console
entry is an explicit execution contract, not a claim inferred from a process
name, PID, OS resource ownership or whether someone else uses the machine.
Do not create a child per check; no worker protocol, codec, watchdog, stable
root, ticket, lease or restart recovery sweep. Normal OS scheduling and native
DB locks; keep check-local close/L1, serial checks and no implicit retry.
External orchestrators can launch the ordinary command for process isolation
and set actual process/container limits. Native crash or OOM may terminate
the whole invocation; no claim of containment or guaranteed completion.

**Embedded scope (maintainer decided 2026-11-27):** M8.1.2 must deliver
adaptive resource management for both standalone and programmatic embedded
usage. Do not defer embedded adaptation or its replacement admission proof
to M8.2. Preserve current RunService and in-process Click capabilities,
exact outcomes, and no unrequested global mutation or termination of host.
Compare the smallest native-first mechanisms: an explicitly authorized
caller-managed native context, ordinary direct execution where noninterference
and private spill are proven, and a standard whole-invocation isolation
boundary only if genuinely necessary. Shared process alone is not unsafe;
do not infer exclusive use from connect success, process name or enumeration.
Do not reintroduce mandatory per-check workers, custom IPC or OS ownership
infrastructure as a default solution. If an option requires a public API
change, transport or subprocess, justify the concrete need, compatibility
and outcome proof before approval. No silent mode switch, setting downgrade,
legacy size-cap workaround or loss of existing supported capability. Both
usage paths must satisfy native control, binding, writer exclusion, actual
noninterference, cleanup, bounded exact results and graceful degradation
before removing the existing guard. M8.2 retains its existing separate
invocation lifecycle and cumulative/concurrency responsibilities.

### Proposed settings and policy semantics

Keep the existing proposed optional project mapping
`execution.scan-budget.local`, config-version 1, all absent by default,
strict positive integer MiB/counts and checked native range, no unknown/
duplicate keys, nonstring path/null/boolean/float, no raw values in errors,
project-relative/absolute existing scratch base, no path expansion, hidden
fallback, or arbitrary default data/row/time cap in managed invocation.
Proposed leaf dispositions (not yet released):
- `max-database-mib`: retain explicit optional physical footprint ceiling
  all nine families, below/equal allowed, over blocked before data reads.
- `warn-estimated-input-rows`: retain optional role-summed catalog estimate
  advisory only, no default threshold or executing preflight; unknown not zero.
- `managed-memory-mib`, `threads`, `spill-mib`: retain explicit native
  maximum targets, not process RSS, CPU quota or physical disk cap; validate
  support and effects, post-connect spill SET where required, actual effective
  value must not exceed authored supported ceiling. If safely lowered based
  on trustworthy facts, warn; cannot silently ignore an explicit control.
- `scratch-directory`: retain explicit existing base; default OS temp base,
  unique private per invocation, no alternate location silently chosen. Keep
  native spill outside DB sidecars.
- `memory-reserve-mib`, `disk-reserve-mib`: propose defer both unreleased
  reserve configuration leaves until concrete demonstrated need; no promise of
  untouched physical capacity or continuous pressure monitor. Explicit memory/
  spill targets already enable user tuning. This requires explicit approval.

Resource observation is optional tuning evidence, not environment certification.
Reuse minimal maintained host available/CPU/disk observations (existing optional
psutil dependency candidate and stdlib disk_usage, native settings), plus
small scoped container hint only if demonstrably necessary for older native
engine behavior. Host data is not container data. Use minimum of trustworthy
relevant finite evidence; partial unknown is not zero/infinity, no exhaustive
ancestor/controller proof or process ownership enumeration. Treat known
unusable required scratch/control as scoped refusal; optional missing metric
warns with practical effect and safe supported choices. No platform/version
allowlist. Compare native recommendation bounded by trustworthy available
headroom with modest memory margin and CPU capacity against native baseline.
Prior measured 75% headroom candidate may be evaluated; 25% reserve/10% disk
reserve are not locked requirements, probe values are not production defaults.
No chosen numerical default until the remaining targeted calibration validates
exact formula, native effect, low/unknown headroom and explicit override.
Disk default prefer verified engine mechanism on selected scratch; older
native cap/SET limitation requires actual effect test, not readback or inferred
quota. No active pressure polling or automatic pressure kill proposed.
Actual native resource failure ERROR; do not retry or misclassify mismatch.

Scratch: create exclusive unique directory under trusted selected base via
standard API, restrict actual access before native reads, use maintained
native privacy primitive only for observed gap (notably older Windows
inherited ACL, POSIX extended ACL), never adopt old folders or scan/delete
unknown entries. Validate actual directory relationship where necessary for
safe cleanup; trusted cooperative environment, not hostile same-user
sandbox. Close native session(s) then normal owned cleanup; never remove a
folder with uncertain current ownership or live use. Known cleanup failure
safe error and existing L1 for affected context; old unrelated residue may
remain after abrupt exit, no claim of orphan discovery or recovery. Retain
unrelated sentinel, reject unsafe explicit base before data; no new global
lock/ticket/FS allowlist, no silent path switch. Operational guidance:
use private user/application temp, external retention policy, do not clean
unknown/live directories. Remaining targeted privacy proof below.

### Outcome and regression disposition proposal

All outcome gates remain mandatory. Mechanism tests can retire only after
explicit approval and corresponding capture/index update, with historical
commits and actual evidence retained. No fabricated test nodes.

| Acceptance | Proposed retain/replace/defer and owner |
| --- | --- |
| A1/R4 | Retain strict config and precedence; defer only two proposed reserve leaves by approval. M8.1.2. |
| A2/R4 | Retain managed all-nine admission/no default cap, explicit footprint ceiling, large-safe vs small-costly. Both standalone and embedded paths required in M8.1.2; prove replacement admission before removing existing guard. |
| A3/R1/R5 | Retain metadata-only optional estimates and independent required binding; no executing preflight. |
| A4/R5 | Retain exact original binding, read-only writer exclusion both orders, sidecar/view/temp/external/alias/path/lease/type guards and precedence; replace worker policy token with matched in-process effective context proof. |
| A5/R1/R8 | Retain exact domain and bounded native result/count shape, no precision loss or LIMIT rewrite; replace IPC cases with existing native result validation. |
| A6/R9 | Retain truthful optional advice, safe terminal/log output on success/fail, no status change; remove mandatory pressure-monitor thresholds, retain actual resource errors and known observation limitations. |
| A7/R5 | Retain all nine families, numeric/type/privacy/precondition behavior and low-level helpers; ordinary native session conformance not worker transport. |
| A8/R8 | Retain config/native error/diagnostic redaction, no raw path/SQL/value; remove worker-frame-specific tests with mechanism. |
| A9/R1/R8 | Retain private evidence and no new output/state/schema/sink changes; preserve embedded/API compatibility; both paths mandatory in M8.1.2. |
| A10/R2/R3 | Replace full controller hierarchy/job/affinity/mount qualification with minimal scoped observation and missing/malformed/denied/future API tests, actual native controls/isolation and scratch privacy; retain host-vs-container limitation. |
| A11/R1/R9 | Retain distinct workload dimensions, compressed/large/skew/null/repeated-scan evidence and advisory only. |
| A12/R4/R10 | Retain constrained/capable measured comparisons, actual disk spilling, full disk, explicit controls and exact results; no fixed SLA/default from CI, no all-version guarantee. |
| A13/R3/R5/R6 | Retain startup cap vs actual SET effect, required native control failure, actual scope/noninterference, normal close and native interrupt/error; remove worker placement proof and pressure termination mechanism. |
| B8/R6 | M8.1.2 native cancel feasibility and accurate stop/cleanup outcomes relied on; M8.2 owns full invocation Ctrl-C/deadline/retry/cancel policy. Remove worker EOF/watchdog/protocol/reap obligations only for absent worker mechanism; no claim of crash containment. |
| B9/R6/R8 | M8.1.2 private scratch/normal and failure cleanup, no unrelated deletion, retained residue/fresh invocation, L1; M8.2 run-wide cleanup. Retire automatic abandoned recovery/tickets/leases only on approval. |
| B10/R7 | M8.1.2 serial check release and refreshed useful scoped facts; M8.2 cumulative/concurrency scheduling; replace one-worker requirement with ordinary owned session, no hidden retry/fallback. |
| P1-P6 | Retain all six compatibility and graceful-degradation outcomes, actual older/current and rolling OS/engine evidence, persistent risk-based CI, future adapter-specific proof and triage. Replace mechanism-specific lanes only, not required outcome coverage. |

R1-R10 all covered by table; M8.3 C10 structured publication, M9.5 type
compatibility, M10.8 scope restoration, M11-M13 and M29 adapter-specific
resource controls/compatibility, later profiling/sinks/integrations retain
assignments. No new milestone; Split Decision: Already Split / Follow Existing
Split. Scope reduction explicit: proposed removal of automatic abandoned
recovery, mandatory per-check worker infrastructure, reserve leaves and active
pressure polling remain proposed scope changes. Maintainer explicitly rejected deferring embedded adaptive execution to M8.2; both usage paths are mandatory here. Other mechanism removals and detailed design still require approval.

| Existing candidate capture IDs | Proposed disposition and replacement |
| --- | --- |
| local-adaptive-resource-targets | Replace formula-specific cases after exact tuning choice; retain units, unknown/zero, overrides and no workload cap. |
| local-resource-observation-hierarchy | Replace exhaustive hierarchy requirement with trustworthy scoped facts, known constrained and partial/unavailable evidence; preserve old native default cgroup mismatch reproducer. |
| portable-resource-observation-uncertainty | Retain portable partial/invalid/missing behavior, simplify platform-specific scope expectations. |
| duckdb-native-resource-control-readback; duckdb-native-spill-setting-effect; duckdb-controlled-owned-session | Retain/reuse native helpers and actual effect, replace worker assumptions with ordinary direct owned session and external reader/writer tests. |
| duckdb-bound-count-result-transport | Retain exact bounded count reader, existing numeric result semantics; no IPC prerequisite. |
| duckdb-worker-lossless-result-transport; duckdb-worker-control-protocol; duckdb-worker-process-lifecycle; duckdb-worker-bound-session-scope | Retire worker-specific codec/framing/EOF/replay/identity cases only if worker removed; replace applicable exact numeric/shape, scope, cancel/cleanup/L1 and invocation noninterference with native tests, preserve history. |
| owned-scratch-two-lease-recovery; owned-scratch-discovery | Retire restart reconstruction and two-lease mechanism only if approved; replace with abrupt exit retains residue, new unique invocation, normal cleanup and no old-file adoption. |
| owned-scratch-untrusted-retained | Retain no-delete-unowned, replace recovery-specific fixtures with actual new owned-directory cleanup/replacement/refusal tests. |
| windows-scratch-private-acl | Retain actual privacy and failure-safe creation; replace persistent native ticket/ancestor cases with minimum required supported primitive and actual old/new Python ACL fixtures. |
| scratch-filesystem-scope-evidence; scratch-namespace-qualification | Replace persistent mount/namespace identity tests with scoped fresh-directory privacy, unknown optional FS evidence, safe cleanup and no unrelated deletion; preserve targeted actual mount/ancestor protection only if demonstrated necessary. |
| local-resource-config-strict-validation (diagnostics-privacy) | Retain strict/redacted config tests, revise only approved leaf list. |
| Pre-existing main capture rows and regression routes | Retain all, including M8.1.1 binding, typed numeric, result, diagnostic, privacy and package compatibility. |

### Implementation responsibility, remaining proof and approval

Reuse config/parser and pure policy seam, native control parser/application,
bounded count reader, existing `_OwnedDuckDbSession` and bound runner where
suitable. Remove experimental worker/protocol/codec/proxy and persistent
namespace/recovery/ticket/mount-specific code only on approved disposition.
Simplify observation and scratch helpers to minimal required functionality;
do not add a second execution service or public adapter API. CLI entry owns
explicit managed invocation contract; service orchestration owns admitted
context/L1, adapter owns native settings/lease/cleanup, check engine owns
normalized policy/outcomes, diagnostics remain sanitized. No data/SQL/raw
native exceptions in terminal advice; warnings do not change PASS/FAIL/error
status/exit. Explicit unsafe mandatory setup -> affected refusal, actual native
failure -> ERROR, no unrelated context block from old scratch. Preserve primary
diagnostic plus cleanup error. M8.3 owns durable projection.

Remaining pre-implementation blockers: (1) select and prove the simplest safe embedded execution mechanism within M8.1.2, alongside standalone execution, and obtain approval of the remaining scope changes above; (2) bounded targeted test of
minimal actual scratch privacy on older Windows and POSIX inherited ACL/
safe parent, no-adoption/no unrelated cleanup, including failed creation;
(3) exact simpler observation/tuning and native spill cap default comparison
on existing constrained/capable workloads, no expansive new OS mechanism;
(4) final exact config/default/diagnostic matrix, regression replacement and
DoD approval. Then test-first implementation from verified baseline/reuse
selected candidate components, exact affected test nodes/capture/index, full
standard CI and persistent representative native matrix, actual negative
proof for critical safety, whole-branch advisory, no gate closure until exit.
No broad new exploration absent concrete failed outcome. Existing runtime
guard and PR suspension remain until approved implementation/exit.

## Historical status and approval boundary (superseded)

Maintainer approved the detailed design and documentation integration on
2026-11-26. Implementation separately approved and in progress; exit proof remains pending. The design is not evidence of implemented behavior
or satisfied gates. M8.1.1 shared binding (PR #38) and targeted M7.4 grouped SQL
correction (PR #39) are verified on main. Split Decision: Already Split /
Follow Existing Split. M8.1.2 is mandatory before M8.2. The existing temporary
64 MiB key/SUM guard remains runtime behavior until replacement is implemented.

Canonical authorities: [ADR 0026](../decisions/adr-0026-local-execution-policy-and-scan-admission.md),
[ADR 0025](../decisions/adr-0025-adapter-aware-execution-advisories.md),
[resource assignments](execution-resource-safety-assignments.md),
[split assignment](milestone-8-split-assignment.md), [M8.1.1 L1](milestone-8-1-1-prework.md),
[scope restoration](execution-scope-assignments.md) and
[type compatibility](type-compatibility-assignments.md). This prework supersedes
the footprint-driven M8.1 historical design only for the remaining resource
policy. Maintain all existing binding, type, prerequisite and privacy rules.

Bounded feasibility probes across the four tested DuckDB versions (1.0.0,
1.3.2, 1.4.5, 2.0.1) establish actual Linux disk spilling, direct worker
termination across Linux/macOS/Windows, calibration on two resource envelopes,
parent-death liveness, native spill limit startup/readback mismatch and local
lock release on process death. They do not establish production IPC, combined
scratch recovery, hard process/physical disk guarantees or universally useful
defaults. Older engines may report host rather than cgroup memory and may
report an ineffective startup spill cap; even post-connect settings have
observed accounting overshoot. Required actual control proof must be measured,
not inferred from setting readback or a green workflow.

## Configuration and precedence

Keep project-owned optional execution.scan-budget.local mapping in recon_project.yml config-version 1, no contract/profile/package/CLI/environment override surface (OS temp base is environment observation, not policy override). Approved configuration keys for implementation, all absent by default:
- max-database-mib: optional hard physical database footprint ceiling, all nine supported project check families, below/equal allowed, over -> existing scan_budget_exceeded; never pretend bytes are scan/work.
- warn-estimated-input-rows: optional positive role-summed catalog estimate advisory, above only; never default arbitrary row threshold or block for unknown.
- managed-memory-mib: optional requested maximum DuckDB engine-managed memory target, can replace automatic native target; not RSS/process cap.
- threads: optional native parallelism ceiling (not CPU quota).
- spill-mib: optional native managed temporary-storage target, not total filesystem bytes or hard physical cap; native SET and monitored spill/free space, no silent hard interpretation.
- memory-reserve-mib and disk-reserve-mib: optional positive reserves for adaptive budgeting/observed pressure; not guaranteed untouched physical capacity.
- scratch-directory: optional existing absolute or project-relative directory (resolve relative to project root, no expanduser/env interpolation or creation of authored parent, verify private safe subdirectory creation and filesystem identity; no implicit alternate location). Default OS temp base; inspect actual filesystem, no automatic use of database sidecar directory. No user-specified classification, allow-unestimated, disable safety, implicit retry, hard process/disk guarantee flag or deadline in this phase. All integer fields strict positive, reject bool/float/null/string/overflow (MiB=2^20 bytes; signed 64-bit ceiling after checked conversion; threads checked against native accepted integer domain, no arbitrary hardware cap in parser). Strict mappings, unknown/duplicate/nonstring keys and invalid path types rejected; empty mappings equivalent absence. No config-version bump proposed, additive field compatibility review and changelog/migration required. Authored explicit ceilings are maximums, not exact minimum resource entitlements; if lowered by independent headroom or CPU, emit safe effective-policy diagnostic (no raw user values unless later explicit allowlisted projection); invalid/impossible required setting or unverifiable explicit native control is refusal, not ignored. Can raise memory/spill/threads above auto by authoring target and adjusting reserve subject to independent effective environment evidence. No hidden auto reconfiguration mid-check.

## Calculations and pressure behavior

Typed snapshots with scope/provenance/availability: host available (not total or free-only), worker/applicable environment headroom, memory and CPU controller scope, actual selected scratch free bytes and filesystem kind, native readback capability, optional workload metadata, explicit policy origin. Linux cgroup v1/v2 from actual /proc/self/cgroup and mountinfo, resolve visible hierarchy/ancestor controller limits and current use, distinguish unlimited from inaccessible, v1 unlimited sentinels, namespace-hidden parent constraints and memory.high as pressure not max; verify child placement matches; Windows/macOS OS available memory and process CPU, Windows job/processor group limits when actually discoverable, macOS applicable process limits; no assumed universal observation. Candidate use psutil for cross-platform host/process observation (optional DuckDB-extra dependency only after install/compatibility proof, no Core dependency; Linux native proc fallback and alternative platform evidence or explicit independent required proof; missing library must not silently break supported low-level use). Native auto settings obtained in isolated worker without opening/scanning user data, then refresh relevant effective resources immediately before admission. Use exact byte/int evidence where available; human-formatted native display rounded interval, use conservative lower edge for ceilings and validate readback interval; no false precision.

Let H=min of trustworthy host available bytes, every applicable finite ancestor max-current (saturating at zero), known independent environment headroom; do not take minimum of unknown as infinity. Known finite zero is not unknown. CPU C=min of available process affinity/cpuset, quota/period across applicable ancestors and platform available CPU count; positive fraction -> ceil(C) executable thread preference, preserve fractional evidence and actual quota distinct; zero/impossible is not a one-thread guarantee. If native N absent but trustworthy H exists, candidate memory target from H; if required H/control evidence absent, default best-effort only if independently proven required protection, otherwise refuse with specific missing proof, not arbitrary fallback cap. Explicit hard OS process/physical quota demands are outside this native-control feature unless separately proven actual scope; never advertise them via config.

Approved initial calibration candidate (subject to implementation-level validation before locking a default): reserve Rm=authored memory-reserve bytes, otherwise ceil(H/4); M=min(authored managed-memory target if present else valid native N, max(0,H-Rm)); when N unknown omit it only with independently proven managed setting support/H. Use integer bytes or conservatively floor in native supported units, never round small positive to a fabricated minimum. This 25% headroom reserve is DuckDB-specific adjustable starting heuristic, motivated by measured auto75 candidate and native buffer-manager blind spots, not a safety invariant or universal percentage. Auto75 tests used different thread tuning; exact final combination not yet measured. Candidate threads T=min(authored or native target, ceil(C)), no default 1 GiB-per-thread rule; validate fractional quota, large CPU machines, low headroom and oversubscription; explicit lower threads retained. If measured target nonpositive, not_executable before scan (resource protection unavailable), no arbitrary file-size substitute. Default disk reserve Rd=ceil(F/10) for actual writable free F, vendor 90% default adapted explicitly even where native readback 0 bytes; authored reserve replaces heuristic. Spill target S=min(authored spill ceiling when present, max(0,F-Rd)), cap by compatible native range and relevant memory-backed scratch headroom. Known tmpfs/memory-backed scratch charged to effective memory as well, not disk extension: account for M and Rm without double-claiming headroom; if no spare spill budget, warn and require independently proven safe native no-spill behavior or refuse if required control missing, offer explicit disk-backed scratch, no hidden path switch or silent disable. Unknown filesystem/quota is uncertainty, not unlimited; no filesystem-wide hard guarantee. Default reserve and tuning are revisable with measured evidence before lock and later M10/M29 gate; user may override. Do not replace prior 64 MiB with any file-derived arbitrary default.

At worker initialization set memory and threads for owned connection, explicitly SET max_temp_directory_size after connection and before transaction/metadata that might allocate/spill, using validated generated setting values; read back all, reconcile version-specific units/rounding and actual support, verify isolated native effects in conformance rather than executing preflight workloads. Runtime check policy based on actual scope, native effective controls and independently observed environment. Recheck observations before actual data work and before next check; no unapproved tuning changes during active statement. Monitor owned worker and actual scratch filesystem (bounded sampling, not a hard quota), separate process RSS, managed limit, cgroup charge, actual file logical sizes vs allocated physical and free space, unknown vs zero. Default memory reserve is tuning margin; warn on measured reserve breach/pressure, request cancellation on independently evidenced critical exhaustion/unsafe observed control breach (finite headroom exhausted, known OS critical-pressure signal, spill observed beyond configured managed envelope beyond verified accounting granularity, actual free disk crossing requested reserve). For default/native-best-effort pressure classification distinguish observed signal from inference; do not kill merely because estimated input large, transient CPU throttling or managed memory readback != total RSS. Explicit reserve threshold is best-effort monitored safety, not a guaranteed physical floor; document possible overshoot/races and observed failure. No default workload timeout or retry/escalation; Ctrl-C and pressure stop supported. Timing/polling and control deadlines are internal safety parameters (not workload timeout), exact values must be tested for slow machines and stop races during implementation. No scheduling redesign. Optional estimate unknown -> no fabricated row warning; issue safe control-availability advisory only if otherwise admitted. Missing mandatory scope/proof or explicit required native setting -> specific refusal; failed setup/native resource/IPC/cancel/cleanup -> ERROR, not mismatch. Preserve primary/precondition precedence and L1.

## Worker, transport and recovery

Choose one fresh owned subprocess per admitted project-run DuckDB check because this path requires native settings isolation and cancellable work; conditional by actual adapter/placement/protection requirements, not database size. Do not impose workers universally on remote adapters or change prepared low-level helpers. No persistent pool/general scheduler; parent keeps existing RunService, CheckEngine, typed operation rendering/comparison/prerequisites, worker holds actual owned read-only session, transaction, private native lease, applies controls and verifies file/catalog/scope before each read. Same _ProjectBoundRunner ownership; extract small collaborators, no separate runner. Existing closure _BoundEvaluation remains in parent; do not pickle/serialize closure, adapter, lease or full profile. Proxy implements private _OwnedSession/_BoundReader seam and owns parent-local identity token mapped to actual child lease; scope includes invocation/session, check id, operation, qualified relations, file identity, policy generation and monotonic request sequence. Setup/handshake, bind, allow matched policy, read count/aggregate, close/abort; no arbitrary external SQL endpoint. Only trusted internal renderer-produced statements through existing path, bound scope/expected fixed result shape and ordered guards preserved. Child rejects wrong family, stale sequence/identity, duplicate/replayed request, changed binding/policy, unsupported transport, extra rows/fields; no data reads before proof. Do not introduce a second SQL parser or claim same-user hostile process security boundary. Use local inherited private pipes, close unrelated handles, launch sys.executable module without shell, no secrets/path/data in argv, no network endpoint, no arbitrary object deserialization. One in-flight request, bounded header and field lengths, validate before allocate, stream/chunk large values, bounded/drained or discarded raw stderr and stdout exclusively framed protocol; no unbounded communicate/log capture. Dedicated parent liveness writer/EOF watchdog; if using shared command channel, single reader thread never blocks behind native query, one in-flight bounded handoff and explicit EOF/abort. Verify actual inheritance on Windows/POSIX. Parent normal stop requests close or cancellation, escalates direct child terminate/kill with bounded wait and actual reaping; never report confirmed stop on request alone. Best-effort parent EOF watchdog proven synthetically; no universal hard guarantee for suspended/GIL-blocked/native processes, external isolation or OS-specific stronger enforcement only if proven and required. If worker exit or cleanup uncertain, latch L1 and block further affected execution. Discard comparison values if protocol/cleanup invalid, preserve safe primary plus cleanup diagnostics. No silent in-process fallback.

Native count-result project path currently calls _read_query_result().fetchall(); replace bound-only count reader with exact expected single-row fixed-column fetchmany(2) validation, no LIMIT rewrite, keep public prepared adapter helper behavior. Existing aggregate already uses fetchmany(2) and bounded DESCRIBE. IPC encoding: explicit closed tagged null, integer sign+magnitude bytes (no decimal string digit limit; adapter native BIGNUM documented max size ~8 MB, derive per-version per-type maximum including native domain and fixed result arity, validate boundaries without imposing a new lower supported numeric ceiling), finite decimal sign/coefficient/exponent/scale from exact Decimal tuple, IEEE binary64 bits for finite/nonfinite/signed zero; no bool/float coercion. Reuse _AggregateQueryResult shape/domain validators parent and child; fixed expected columns/domains; counts exact integers. Frame limit from schema + proven native-domain max, not a magic small generic cap; request bound from existing accepted typed plan/renderer/domain lengths, no new hidden identifier/check-plan size restriction; if unsupported/incomplete bounds stop for design correction, not silently shrink supported BIGNUM. No public serialization, no raw payload in diagnostics. Child must not generate a new reconciliation interpretation or change public compile renderer. Tests must preserve native domains including >4300-digit integer, maximal supported shape boundary and invalid/overlong frames.

Owned scratch protocol (trusted cooperative local filesystem, not hostile sandbox): create per-invocation private namespace and unique random per-session directory under approved existing base, owner-only permissions/ACL where supported, check identity and symlink/junction/reparse-point/no traversal; no arbitrary existing-directory adoption or sweeping. Stable per-user/per-project private root with coordination lock outside session directory, ownership metadata contains no SQL/paths/data/secrets, unique session identifier and protocol version. Serialize create/claim/recover using root coordination lock; parent acquires parent lease before publishing session, worker acquires separate worker lease under root lock before native open, verifies exact directory/marker identity and ownership, acknowledges before parent proceeds. Both hold independent exclusive OS locks for their full usage, no inheritance/early unlock; root lock only short coordination, not held while query runs. Parent crash before worker handshake: cleaner obtains root lock and both session leases only if inactive, closes lock handles before removal under root lock (Windows deletion semantics); late worker must acquire root lock and revalidate directory identity/marker before any open, otherwise exits; no gap allowing deleted directory recreation. Normal cleanup requires confirmed worker exit, native cleanup evidence, correct ownership and lock/identity proof; remove only owned session scratch. Abnormal parent loss: EOF stop best effort, OS releases worker lease when stopped; on next run recover only positively identified abandoned owned sessions after exclusive root+both-lease proof and no live owner, never PID/age alone. If namespace/filesystem/permissions/ownership/locking uncertain, do not delete; quarantine/retain and sanitized warning or L1 error depending on current affected execution. Do not promise immediate disk cleanup after parent kill, do not touch DB sidecar, target/report/state outputs, unrelated directories. POSIX flock and Windows msvcrt lock primitive proved; complete two-lease/root coordination protocol, network/unsupported filesystem refusal, Windows sharing, race/crash during marker publication, incomplete marker, symlink replacement, concurrent invocations and crash during deletion require real tests before exit. No broad automatic cleanup, no stale-result artifact policy moved forward.

## Scope, responsibility map and gate consequences

Move only B8 stop request/confirmed exit/parent liveness for one owned worker, B9 native/IPC/owned scratch cleanup and safe crash recovery, B10 single active worker and resource snapshot scope into M8.1.2 as explicit prerequisite. M8.2 retains invocation identity/timing, cumulative budgets/concurrency/fanout, general deadlines, retry and cancellation lifecycle, full plan/orchestration, no duplicate implementation; M8.3 owns C10 serialized policy/effective/observed/unavailable/advisory/enforcement/cancel/cleanup and safe publication. M8.1.2 no outputs other than approved owned scratch and existing terminal behavior plus additive safe diagnostics; no run_results/evidence/report/state/sink outputs. Scope restore/type retrofit remain M10.8/M13.5/M18/M29 and M9.5. No new adapters or cross-context/row-level/selector/sampling, no SQL rewrite/hidden retry/new data movement. No universal claim for Windows/macOS/Linux filesystems or remote engines. No hard deadline, process or physical disk guarantee unless native OS control actually proven.

Responsibility map (planned paths; reuse existing files when appropriate): config/project_config.py plus focused private execution-policy parser owns strict schema and immutable requested policy only; no probes. check_engine/scan_budget.py pure canonical policy owns allow/refuse/reason/advice/effective policy calculation from typed evidence; no OS/SQL; retain public low-level classifier compatibility while replacing equality-based project aggregate reconstruction with matched typed admission, no forged boolean. services/run.py existing setup/preselection and _ProjectBoundRunner handoff; remove duplicated 64 MiB check at both call sites, preselection not final decision; do not let row-count runtime overwrite specific explicit-budget reasons. services/_bound_runner.py orchestrates one session, scope/admission, L1 cleanup and safe diagnostic attribution, no direct SQL/control syntax. adapters/_project_binding.py private neutral session/proof contract, separate private resource observation provider (platform-specific facts, not policy), DuckDB _bound_execution.py and focused native control collaborator own startup/SET/readback, transaction/lease, real native reads; worker/proxy/codec/scratch modules private cohesive collaborators own process, protocol and scratch lifecycle only. check_engine/runtime.py/execution.py/key_safety.py/aggregate.py preserve semantics, renderer ordering, actual matched proof, low-level prepared helpers and public imports; no duplicated policy/alternate execution. cli/main.py/services/results.py render existing run result and safe advisory diagnostics even successful runs, no change in exit/status meanings or compile CLI behavior; inspect actual output route. Keep adapter-specific imports out of Core engine/service orchestration, no public adapter signature/capability/typed plan/artifact schema change. Introduce psutil dependency only after explicit compatibility/import/installation decision; no mandatory Core dependency. Existing anti-pattern findings: duplicate footprint guard in RunService/_ProjectBoundRunner, aggregate decision canonical-equality reconstruction, unbounded count fetchall in project bound path, potential raw config diagnostic field leakage, row-count generic refusal masking reason. Same-scope design correction required, no broad refactor. Review existing low-level historical guard separately and preserve behavior until explicit future decision.

## Acceptance and conformance matrix

All A1-A13 remain mandatory; each variant below is a required parametric case, not just a sample. New test paths and function names are proposals to reconcile to actual pytest nodes before exit. Every row also checks existing result/no-write/privacy semantics and retains matching legacy native suites. R1-R10 and B8-B10 subset mapping explicit.
| Family | Cases and expected behavior | Planned exact test nodes / owner |
| --- | --- | --- |
| A1/R4 | absent/empty each mapping, all authored leaves independently/mixed, min/max/overflow/zero/negative/bool/string/float/null/non-string/duplicate/unknown keys, malformed mapping/path, explicit target/reserve precedence; config invalid before profile/native work, no raw input | tests/config/test_project_config.py::test_local_resource_policy_defaults ; ::test_local_resource_policy_values ; ::test_local_resource_policy_invalid ; ::test_local_resource_policy_precedence |
| A2/R4 | no default footprint restriction on all nine families, explicit below/equal/one byte above including row-count, large file small work, small file costly compressed, existing small fixture, author raises/lowers target; hard footprint block zero scans, no default row cap | tests/check_engine/test_execution_boundaries.py::test_project_footprint_policy ; tests/services/test_run_service_duckdb_execution.py::test_adaptive_local_admission ; ::test_explicit_footprint_all_families |
| A3/R1/R5 | catalog available zero/positive/stale/negative/malformed/overflow/absent/unsupported/throw, role sum even same relation, required binding metadata failure distinct; no COUNT/EXPLAIN ANALYZE/unsafe storage probes before comparison; optional unknown not zero or blanket block | tests/adapters/test_runtime_safety.py::test_nonexecuting_resource_evidence ; tests/check_engine/test_execution_boundaries.py::test_optional_estimate_does_not_authorize_or_block |
| A4/R5 | same context/aliases/base tables/RO verified, missing/symlink escape/sidecar/views/attached/temp shadow/external/in-memory/cross-context, wrong stale or forged policy/lease/operation/scope/generation; unsupported typed plan/capability/profile/lifecycle/precondition precedence; no data query | tests/adapters/test_duckdb_bound_execution.py (existing suite plus ::test_bound_policy_identity) ; tests/services/test_run_service_bound_execution.py::test_resource_preflight_no_scan ; ::test_resource_preflight_precedence |
| A5/R1/R8 | distinct file/work/rows/result/transfer/actual memory and disk, unknown vs zero, bounded count and aggregate shape zero/one/two rows, extra column, oversized frame, native big integer and decimal/no precision loss, no LIMIT rewrite | tests/adapters/test_duckdb_aggregate_transport.py (existing + native domain extremes) ; tests/adapters/test_duckdb_resource_worker.py::test_bounded_typed_transport ; ::test_count_reader_rejects_extra_rows |
| A6/R9 | estimates below/equal/above/absent, actual pressure known/unknown, reduced authored target, pass/fail/error with advisory, hard block with warning candidate, distinct/dedup messages; warning not reconciliation WARN, no implicit filtering/sample/SQL rewrite, future suggestions honest | tests/check_engine/test_execution_boundaries.py::test_resource_advice_precedence ; tests/cli/test_main.py::test_run_resource_advisories |
| A7/R5 | all nine native check families, exact integer/decimal/BIGNUM/native float/nonfinite/signed zero, nullable/composite keys, strict types, group presence/empty/tolerance/named override, low-level prepared helpers unchanged, unsupported families unchanged, no missing proof bypass | existing tests/check_engine/test_aggregate_execution.py ; tests/adapters/test_duckdb_aggregate_numeric_domains.py ; tests/services/test_run_service_aggregate_admission.py ; tests/services/test_run_service_bound_execution.py::test_worker_all_supported_check_families |
| A8/R8 | secret/path/identifier/SQL/native error/value sentinel in config, probe, worker stderr/protocol, setup, warning/cancel/cleanup, malformed response; safe fixed diagnostics and preservation of primary error | tests/services/test_run_service_adapter_lifecycle.py::test_resource_diagnostic_privacy ; tests/adapters/test_duckdb_resource_worker.py::test_worker_output_redaction ; tests/cli/test_main.py::test_run_resource_privacy |
| A9/R1/R8 | immutable private requested/effective/observed/advisory/provenance/unknown scope; no new public signatures, compiled artifact or run_results/evidence/report/state/sink writes; successful/error/cancel/no-check runs leave existing sentinels untouched except owned scratch | tests/check_engine/test_execution_boundaries.py::test_private_resource_evidence ; tests/services/test_run_service_duckdb_execution.py::test_resource_policy_no_output_writes ; existing tests/compatibility/test_python_package_exports.py |
| A10/R2/R3 | Linux v1/v2 finite/unlimited/zero/missing/namespace hidden/ancestor tighter/current pressure/mountinfo escaped paths, host vs cgroup, CPU fractional/affinity/cpuset/quota, Windows job/processor group/macos observations available or partial, malformed/permission/probe failure, actual scratch disk/tmpfs/unknown, startup vs SET/version readback/isolation | tests/adapters/test_local_resource_observation.py::test_effective_memory_evidence ; ::test_effective_cpu_evidence ; ::test_scratch_filesystem_evidence ; tests/adapters/test_duckdb_resource_worker.py::test_native_control_application |
| A11/R1/R9 | compressed small costly vs big safe, narrow/wide/skew/null/repeated scans/join intermediates, estimated versus actual/unsupported costs, no unjustified hard inference, advisory only when supported | tests/check_engine/test_execution_boundaries.py::test_resource_dimensions_independent ; tests/adapters/test_duckdb_resource_worker.py::test_real_workload_evidence |
| A12/R4/R10 | constrained and capable representative CPU/RAM/disk, actual larger-than-RAM file plus independently observed disk spill, actual final SQL all relevant pins, memory pressure and changing headroom, final candidate reserve and threads compared to native-adjusted baseline, explicit overrides, small costly, no fixed SLA or arbitrary cut, record exact result/peak/use/errors/clean | tests/adapters/test_duckdb_resource_worker.py::test_adaptive_resource_calibration ; ::test_large_safe_and_small_costly_workloads ; bounded validation-only CI if costly, permanent representative regression tests and native conformance |
| A13/R3/R5/R6 | native startup cap ignored despite readback (observed), post-connect SET/control malformed/unavailable/error, overshoot/accounting/actual disk pressure, wrong worker placement/scope, parent isolation, unavailable hard enforcement not claimed, controlled error and confirmed stop, no fallback | tests/adapters/test_duckdb_resource_worker.py::test_spill_setting_effect_not_readback ; ::test_worker_settings_isolation ; ::test_required_control_failure ; ::test_native_pressure_stop |
| B8/R6 prerequisite | stop requested vs confirmed, Ctrl-C/pressure, worker startup/IPC EOF/timeout/crash, parent death before/after handshake/during query/pipe inheritance, process identity and termination races, lost/malformed/duplicate response, no result if unconfirmed | tests/adapters/test_duckdb_resource_worker.py::test_worker_termination_confirmation ; ::test_parent_death_liveness ; ::test_worker_protocol_failure |
| B9/R6/R8 prerequisite | normal/error/cancel/crash, active lease conflict, root+parent+worker lock race, late child after recovery, Windows sharing, lost/malformed markers, unknown FS/symlink/junction/replaced identity/concurrent invocation/crash during delete, no deletion of live/unowned, primary/cleanup precedence, L1 latch | tests/adapters/test_resource_scratch.py::test_owned_scratch_recovery ; ::test_scratch_live_owner_races ; ::test_untrusted_scratch_never_deleted ; tests/services/test_run_service_bound_execution.py::test_worker_cleanup_latch |
| B10/R7 prerequisite | one worker per check, no next query until stop/release confirmed; per-check re-observation, concurrent external invocations distinguished not global reservation, no hidden retry or scheduler; full cumulative B10 remains M8.2 | tests/services/test_run_service_bound_execution.py::test_single_worker_and_refresh ; ::test_no_fallback_or_retry |

BDD: default project with file larger than RAM completes using exact spill where supported; same contract on two machines gets different effective settings but exact same comparison; explicit footprint over limit refuses before native data query; unknown catalog estimate with proven required control executes, warning not mismatch; small compressed costly query can error without false FAIL; actual pressure triggers safe stop, no comparison values if failure; explicit native cap applied and reported as managed not physical quota; observer connection unchanged; parent abrupt death stops worker best effort and next run only recovers proven inactive scratch; uncertain cleanup stops subsequent affected work per L1; malformed worker frame cannot expose values or become pass; all scenarios preserve no hidden sampling/retry/outputs. Future adapter R1-R10 disposition and M29 promotion remain mandatory; no DuckDB mechanism forced.

Regression review: existing index routes adapter_runtime, scan_safety, check_engine, execution_result, typed_check_plan, prerequisite_blocking, diagnostics, redaction, source_target_privacy, CLI/terminal, artifact_lifecycle, validation defaults and package imports as affected. Preserve existing capture rows duckdb-owned-project-binding, project-binding-check-local-cleanup, duckdb-private-grouped-join-performance, duckdb-private-bounded-aggregate-transport, duckdb-private-typed-numeric-transport, duckdb-private-aggregate-native-domain-guards, duckdb-private-bounded-grouped-summary, aggregate-runtime-scan-preflight/private-routing/capability-isolation, aggregate-native-service-lifecycle, key-safety prerequisites/shape/case/relative path/view/sidecar, aggregate-service-output-privacy, yaml-diagnostic-redaction and compile-command-terminal-contract. Required new capture candidates for startup spill readback mismatch, old native auto memory ignoring cgroup, permissive large safe vs costly small, worker isolation/abnormal stop and scratch ownership, exact large numeric IPC and bounded count result. Do not create fabricated pending pytest nodes now; implement test-first and actual markers/status with carryover gates. Whole branch advisory/capture metadata must run or exact API equivalent at exit, no script-executed claim now. These are implementation obligations, not completed test or capture evidence. Do not promote existing or new capture status without actual proof.


## Outcome and diagnostic contract

Use existing configuration error taxonomy for malformed YAML and settings
(`RC_CONFIG_INVALID_PROJECT_CONFIG`); suppress unknown authored field values
and untrusted native text in newly introduced diagnostics. Preserve existing
placement, prerequisite, artifact, capability and L1 precedence. The
following codes are approved planning names for implementation; wire through
the existing diagnostic owner and review the public inventory before release.

| Case | Expected outcome and safe code |
| --- | --- |
| Explicit physical footprint over ceiling | not_executable / scan_budget_exceeded / RC_RUNTIME_SCAN_BUDGET_EXCEEDED; no data read |
| Required binding unavailable | not_executable / bounded_local_scan_required / RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED; no data read |
| Unsafe executing preflight | not_executable / unsafe_scan_preflight / RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT |
| Required resource evidence/control unavailable before work | not_executable / existing bounded_local_scan_required reason, RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE; no data read |
| Explicit estimate threshold exceeded after admission | existing comparison status, RC_RUNTIME_SCAN_ESTIMATED_INPUT_ROWS_WARNING |
| Best-effort observation limitation or reduced effective target | existing comparison status, RC_RUNTIME_RESOURCE_ADVISORY |
| Setup or native data execution failure | error / existing RC_ADAPTER_CONNECTION_FAILED or RC_ADAPTER_QUERY_FAILED; safe fixed message |
| Observed resource exhaustion or pressure cancellation | error / RC_RUNTIME_RESOURCE_EXECUTION_FAILED; no comparison values |
| Invalid transport or binding drift | error / RC_RUNTIME_BINDING_PROOF_FAILED or RC_RUNTIME_AGGREGATE_RESULT_INVALID (numeric evidence), no raw payload |
| Worker stop unconfirmed or native/scratch cleanup fails | error / existing RC_ADAPTER_CLOSE_FAILED, L1 RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE for subsequent affected checks; preserve primary diagnostic |
| Abandoned scratch cannot be safely recovered | RC_RUNTIME_RESOURCE_ADVISORY if independently safe new execution; otherwise L1 error; never delete uncertain ownership |

Unknown optional metadata is neither zero nor a hard admission reason.
Missing required proof cannot be converted to a warning. Explicit footprint
limits cover row count as well as key and aggregate families; this is an
opt-in restriction, not a default change. Existing prepared adapter helpers
retain their current behavior. No stable public reason enum or signature
addition is needed for this design; if implementation finds existing
taxonomy cannot express required behavior, reopen compatibility/design review
rather than silently coerce it. Warning diagnostics must be emitted safely on
success and failure without changing status or exit category.

## Implementation sequence and test plan

1. Test-first strict config, pure policy and observation, including A1-A4,
   A6, A10-A12 and the actual candidate reserve/thread comparison. Decide
   portable observation dependency and exact native units from real proof;
   no new Core dependency without compatibility review.
2. Test-first bounded count and numeric transport, native owned session and
   worker, including A4-A5/A7-A8/A13 and B8 prerequisite. Retain existing
   aggregate guards, compare semantics and renderer.
3. Test-first scratch ownership, abnormal stop and cleanup, B8-B10
   prerequisites, A8-A9/A13; prove full coordination, liveness and L1
   before relying on them for admission.
4. Integrate single project policy in RunService and existing runner, cover
   all nine families, advisory presentation, no outputs and legacy helper
   compatibility; prove no fallback and no duplicate policy.
5. Run representative constrained/capable synthetic and actual bound SQL
   validation across supported pins and platforms; revisit candidate tuning
   or unsupported protection before locking defaults. Complete gate,
   compatibility, diagnostics inventory, configuration/user documentation,
   migration and changelog review for implemented behavior; add actual
   regression captures and carryover assignments, not fabricated nodes.

## Gate review, compatibility and exit criteria

- Gate 4L: all R1-R10 and A1-A13 plus B8-B10 prerequisite cases above,
  including actual native setting effects, no data scans on refusal,
  useful measured defaults and precise distinction of hard/managed/observed
  control. Gate 4I: actual local binding and independent bounded transport,
  no scope expansion or remote placement. Gates 4A/4B/4C/4J: existing
  plan, adapter, capability and diagnostic restrictions. Gate 5 and L1:
  confirmed stop, cleanup, isolation and failure precedence; run-wide
  lifecycle remains M8.2. Gate 5E: no artifact writes; owned scratch only.
- Gate 1A/ADR 0014: dependency blockers unchanged; Gate 3F2/Gate 6:
  safe diagnostics and no raw SQL, paths, rows, values or credentials;
  Gate 4O/8C: exact native integer/decimal/float and conformance retained,
  no precision downgrade. Gate 4P/M9.5 and Gate 4Q/M10.8/M13.5/M18/M29
  remain mandatory, not waived by this phase. Type and scope expansion
  not applicable to this phase because it changes policy, not admitted
  types or endpoint classes. Gate 3L and M12.5 deeper profiling not
  implemented; optional non-executing estimates only.
- All matrix variants have actual pytest nodes, positive/negative and
  real native conformance evidence; parameterize cross-family, supported
  versions, Python 3.11/3.12/3.13 and relevant supported platform/filesystem
  differences. Prove actual larger-than-RAM spilling and costly small
  workloads, low/full scratch and abnormal stop, actual control effects
  and exact result equivalence. CI measurements are not an SLA or proof
  of universal tuning. Any required unknown/unsupported protection is
  a blocker for the affected capability; no silent downgrade.
- Existing public compatibility and package exports remain stable; additive
  project config and safe diagnostics require documented compatibility and
  migration; update actual affected durable docs and changelog with
  implementation, not claim planned behavior is already available.
- Complete relevant pytest and pinned native lanes, lint/format/type
  checks, pre-commit, regression-capture metadata and branch-wide advisory
  checks; cumulative review of exact head, all applicable gate assignments,
  privacy/no-writes and cleanup. When local validation is unavailable,
  equivalent CI/API proof is allowed; use bounded synthetic validation only
  and remove temporary files. No weakened evidence or approval.
- M8.1.2 exit requires actual integrated proof and separate exit approval,
  no open mandatory variants, no unassigned regressions; M8.1 umbrella
  exit follows both children and correction. B8-B10 remaining run-wide
  lifecycle in M8.2 and C10 publication in M8.3 remain mandatory.
  Re-evaluate R1-R10 for every adapter/version/placement expansion and
  M10 readiness, M29 promotion; no DuckDB-specific requirement imposed
  universally.

## Readiness verdict

Design approved for documentation integration. Implementation is authorized and in progress; exit approval is pending. The candidate reserve and thread algorithm, native
observation/dependency choices, complete IPC/domain bounds, full scratch
ownership and lifecycle proof must be verified during implementation and
before exit. If a required mechanism cannot be safely implemented, stop for
design correction and approval; do not narrow capability or mark gates done.

## Mandatory platform compatibility acceptance (P1-P6)

Apply the [Gate 4L platform subfamilies P1-P6](execution-resource-safety-assignments.md#mandatory-platform-compatibility-and-graceful-degradation-gate-4l) in addition to every existing A/R/B obligation. This is an approved refinement of this phase, not a new runtime allowlist or a scope expansion.

| Family | Required variants and expected behavior | Planned test ownership (existing or to implement) |
| --- | --- | --- |
| P1 / A2,A7,A10 | Unknown/new/older OS or compatible engine/dependency version with verified required controls; exact comparison succeeds, no version-label-only refusal or warning. | tests/services/test_run_service_resource_policy.py::test_untested_platform_with_verified_controls; native worker conformance |
| P2 / A3,A6,A10 | Missing/changed/denied/malformed host, cgroup, job, CPU, filesystem or optional estimate API; keep independent trustworthy facts, unknown distinct from zero, continue with actionable advice if required protection independently proven. | tests/adapters/test_local_resource_observation.py; tests/adapters/test_portable_resource_observation.py; tests/services/test_run_service_resource_policy.py::test_partial_observation_advisory |
| P3 / A4,A13 | Required control absent, ineffective readback, unsafe scope or missing proof; independently verified equivalent mechanism at the same scope or affected check refusal before data read; actual resource failure ERROR; preserve unrelated checks and L1. | tests/adapters/test_duckdb_resource_worker.py::test_native_control_application; tests/services/test_run_service_resource_policy.py::test_required_control_unavailable_or_verified_alternative |
| P4 / A6,A8,A9 | Warning on successful or failing run explains missing dimension, consequence, decision and supported recovery; terminal/captured logs, bounded deduplication, sanitized diagnostics; no comparison/exit change from advisory alone. | tests/cli/test_main.py and tests/services/test_run_service_resource_policy.py::test_resource_advisory_terminal_and_privacy; M8.3 structured publication |
| P5 / A10,A12 | Distinct older/current OS images per applicable family, actual version/build/architecture evidence, Python and native pins, constrained/capable and unsupported cases, actual native controls and lifecycle, synthetic future/API-change variants. | native observation/worker/scratch tests; persistent compatibility CI and exact run/job proof |
| P6 / A12 | Persistent pinned and rolling matrix, periodic/on-demand/change/release checks, failure triage, supported regression capture, recorded coverage gaps and next gate. | CI workflow and compatibility matrix; branch-wide regression advisory and exact test nodes |

These are planned node names where tests do not yet exist; replace with exact
implemented nodes and native evidence, not invented passing tests. Existing
portable observation unit tests alone do not satisfy P1-P6. Complete the
persistent multi-version CI workflow and run it on the exact integration
revision before exit. User-facing CLI/config/limitations documentation and
changelog must describe actual supported alternatives, warnings, best-effort
versus required protection, and tested versus untested versions. Do not
advertise these features as available on main before implementation merges.
