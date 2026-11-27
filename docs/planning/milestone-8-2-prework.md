# Milestone 8.2 - Execution Planning And Run Lifecycle

## Initial preflight (not design approval)

Base: 40e756209b80a267674f7376c6bd4db81c6a7214, verified scoped M8.1 exit. Follow the
[split assignment](milestone-8-split-assignment.md) B1-B10 and
[resource safety assignments](execution-resource-safety-assignments.md).
Split Decision: Follow Existing Split. No runtime implementation authorized.

### Initial source findings

- `services/run.py::RunService.execute` generates a run ID and starts timing
  only after configuration, artifact loading and runtime setup. It supplies
  the finish timestamp before calling the engine. Early failures have only
  command diagnostics. B1 must represent invocation and cleanup truthfully.
- `check_engine/engine.py::CheckEngine.run` recursively resolves and caches
  prerequisites; preserve at-most-once evaluation and ordered result identity.
  Avoid another runner or independent status aggregation.
- `check_engine/models.py` already owns check/contract/run status precedence;
  preserve executed versus non-executed distinctions and existing no-check
  semantics. `services/run.py` currently maps outcomes to command results
  and deduplicates diagnostics; keep distinct primary and cleanup evidence.
- Existing native owned sessions implement interruption request, confirmed
  close, private scratch cleanup, per-check fresh resource observation and
  affected-database isolation. Invocation orchestration must reuse them.
- Current load-only behavior does not automatically parse or compile. B2 must
  explicitly settle freshness/compile policy before any change. No hidden
  rebuild or silent stale-artifact acceptance decision in this checkpoint.

### Remaining design and proof obligations

| Family | Required design and acceptance focus |
| --- | --- |
| B1-B2 | Invocation identity, true lifecycle timing and failure stages; explicit plan, freshness and compile/load behavior. |
| B3-B4 | All existing statuses, mixed outcomes and dependency ordering; setup, native failure, cleanup failure and diagnostic identity/precedence. |
| B5-B7 | Preserve verified admission and safe advisories, whole-project scope and future selection readiness, typed privacy-safe in-memory metadata; no new writes. |
| B8-B10 | Requested versus confirmed cancellation, deadline/timeout and retry policy, abrupt termination and cleanup uncertainty, cumulative budget scope and bounded scheduling; reuse existing native protections. |

Before design lock: review Gates 5, 4I, 4L, 3F2, 6, 4J, 1A, 4P and
selector/sink readiness; ADRs 0014/0021/0022/0025 and current result/CLI/artifact
contracts; regression capture index and matching rows. Expand concrete
acceptance variants, BDD, source/responsibility map, tests, compatibility and
privacy impacts, research decisions, scoped gate dispositions and Definition
of Done. Preserve M9.5 type and later scope/adapter ownership. Do not restore
worker/IPC, automatic recovery or arbitrary admission limits. No selectors,
new comparison operations, run-results writer, evidence or sinks. M8.3 owns
publication and final CLI mapping. No default deadline/retry/concurrency
policy is selected by this initial audit.

## Maintainer-approved design direction (historical proposal text)

The maintainer approved this direction; it does not authorize runtime implementation. ADR
[0027](../decisions/adr-0027-run-lifecycle-result-semantics-and-exit-codes.md)
records the approved direction and detailed interface refinement below. Keep the existing milestone split: lifecycle
and native stop coordination are cohesive; publication and broader
execution remain separate. No new executor, process worker, scheduler,
global resource manager or persistent recovery infrastructure.

### Decision and behavior

1. One invocation identity allocated before preparation, using the existing
   random run-ID convention. UTC start/finish labels and monotonic elapsed
   duration include configuration, artifact load, runtime setup, execution,
   native cleanup and finalization. Early failures receive an invocation
   envelope; unknown project/plan is absent, not fabricated. Clock rollback
   cannot create negative elapsed time.
2. Explicit compile then run remains the default. Existing structural and
   matching-artifact checks remain mandatory; malformed/missing/inconsistent
   inputs fail with no native read. No automatic parse/compile, cache,
   timestamps-as-freshness proof or claim of authored-source freshness.
   M10.5 owns semantic freshness/fingerprints. Report compiled scope, not
   current authored project equivalence. No new output files.
3. Existing engine owns prerequisite resolution and at-most-once evaluation;
   explicit immutable in-memory plan identifies loaded checks, dependency
   graph and whole compiled scope, without SQL/profile/data values. Preserve
   artifact order for presentation; do not introduce a second graph engine.
   Keep planned and actual admission/placement/availability separate.
4. Preserve existing check/contract/run status aggregation and command
   mappings. Invocation lifecycle is separate from check status: setup or
   cancellation failure must never aggregate to successful/no-check outcome.
   Completed valid results remain distinguishable from interrupted and
   unstarted work. Active interrupted checks are runtime errors without
   comparison values; remaining planned work is not executed with an explicit
   cancellation/deadline reason (proposed additive reasons, not a new
   status family). No misleading skipped-by-selection or prerequisite reason.
   Preserve primary failure and cleanup failure independently.
5. Proposed optional positive integer invocation timeout in seconds, explicit
   command option and equivalent embedded argument; default absent, no new
   resource YAML keys or environment precedence. Exact option name proposed
   `--timeout-seconds`; reject zero, negative, bool, invalid and native
   conversion overflow. Deadline is monotonic, shared from entry to
   completion, never reset per check. Expiry requests stop; no new check or
   native statement starts after stop is observed. Deadline is not a hard
   bound on process termination; required cleanup may outlast it.
6. Embedded cancellation is cooperative and invocation-local (caller-owned
   cancellation signal/token; exact API to be approved), no library signal
   handler or process-wide cancellation. CLI Ctrl-C must use the same
   lifecycle path where supported; distinguish delivery/request, active
   native interrupt, executing-call return, confirmed stop, confirmed close
   and cleanup. Request alone is not proof. On cancellation during setup,
   execution or cleanup, retain truthful outcome and do not close a live
   native call. Race with completed work resolved by one lifecycle owner;
   a stop before finalization cannot be misreported as successful complete
   reconciliation. Native interruption is adapter-owned; use existing
   session, not a second executor. Prove request/launch and completion races
   and real CLI signal behavior on supported platforms before claiming
   responsiveness. No force-kill, external-process protection guarantee or
   daemon orphan; if required cancellation cannot be safely proved, stop
   implementation and revisit design rather than silently weakening scope.
7. Serial native check scheduling (one active native check per invocation),
   with adaptive native threads retained. Shared elapsed budget across all
   work; track check attempts and elapsed/observed facts separately from
   estimates and managed memory/spill targets. No arbitrary check-count,
   total-row, file-size, cumulative CPU/memory/disk default or invented
   physical consumption. Actual cumulative scan/transfer/cost/physical
   limits not available in this scope; retain explicit unknown/unsupported
   dimensions and future adapter/multi-context gate assignments. No
   concurrent check fan-out until separately justified/proven. No automatic
   retry, backoff, escalation or replay of a changing snapshot; external
   callers may explicitly start a fresh invocation. Retain affected-database
   cleanup isolation for ordinary failures, stop all new work for invocation
   cancellation, and retain unverified scratch rather than sweep it.
8. No stable new serialization, raw RunResult export, public result artifact
   or sink. Keep existing ServiceResult fields, dict and exit behavior;
   proposal is a typed, privacy-safe in-memory invocation outcome/metadata
   handoff behind existing service boundary, no source/target values, raw
   estimates/SQL/plan text, paths, native errors or profile payloads. Preserve
   existing bounded internal comparison data behavior. M8.3 owns versioned
   allowlisted publication and final terminal projection. Non-run commands
   must remain unchanged.

### Dimension-expanded acceptance and test plan (proposed)

All test entries below are required cases, not claims of existing tests.
Use the existing test suites and capture rows before adding narrowly scoped
new nodes. Test-first; actual RED for critical false-success, cancellation
race, missing cleanup and budget enforcement defects. Each implementation
slice and final cumulative phase uses review-fix-revalidate.

| Family | Dimensions / required cases | Expected behavior and proof owner |
| --- | --- | --- |
| B1 | Success/fail/warn/error/empty; config/load/setup/engine/cleanup errors; clock jumps, subsecond duration, repeated invocation | One ID, full monotonic duration and true finish, absent unknown metadata, no false completion. Service tests with controlled clocks and real delayed cleanup. Gate 5. |
| B2 | Valid/missing/malformed/unsupported-version/mismatched artifacts, duplicate IDs, mixed empty/nonempty, authored YAML edited/malformed, concurrent artifact change | Preserve existing loader validations; no auto-compile/write or stale-current claim. Snapshot loaded plan and validate required bindings at execution. Artifact/service tests; freshness/cache proof later. Gates 5/5E. |
| B3 | All seven check statuses and eight aggregate statuses, pairwise precedence, empty/mixed, missing/cyclic/failed/unsupported prerequisite, repeated shared prerequisite | Existing model remains authoritative, one result per planned check; no silent skip, no double execution. Engine/model tests; Gate 1A/5. |
| B4 | Config/setup/factory/capability/native/query/rollback/close failures; same versus different connection/session diagnostics; primary FAIL/ERROR plus cleanup failure | Preserve stage, reason and independent diagnostics, no result values on invalid outcome, same-context uncertainty does not poison unrelated work. Existing adapter/service tests plus invocation-level cases. Gates 3F2/4J/5/6. |
| B5 | All nine supported check families, supported/unsupported capability and placement, hard admission failure, optional unknown estimate, explicit resource setting, reduced targets, true mismatch | Existing guard executes no hard-blocked scan, warning cannot change comparison status or override hard refusal. Existing native/aggregate suites, actual supported versions. Gates 4I/4L/4P/8C. |
| B6 | Whole compiled scope, multiple contracts, dependency ordering, empty plan, plan vs completed count after stop, future selected scope representation | Scope truthful; no selectors or fabricated full-project freshness; no sink/artifact references invented. Engine/service tests. Selector readiness. |
| B7 | Embedded/CLI, all failure stages, secret/SQL/plan/path/relation/value canaries, diagnostic code/severity/hint, old service dict, preexisting outputs | No raw payload projection, no new generated files, no changes to prior artifacts or unrelated commands; preserve privacy and command contract. Gates 3F2/4J/5/6/5E. |
| B8 | No timeout, explicit valid/invalid, before setup/query, between checks, active spilling query, interrupt failure, cancellation vs query launch/return/finalization, repeated request, Ctrl-C, non-main-thread embedded, abrupt kill | Request and confirmed stop distinct; shared deadline, no new work after observed stop, no premature success/release. Native actual tests on four pins and platform matrix; deterministic race tests and CLI subprocess/embedded proof. Abrupt process loss no returned result, no cleanup guarantee. Gate 4L/5/P1-P6. |
| B9 | Normal release, rollback/close/scratch failure, interruption during cleanup, multiple affected aliases/unrelated DBs, abrupt residue, repeat invocation | Close only after executing/interrupt calls return; retained uncertain scratch; preserve primary failure; no adoption/sweep; ordinary affected-context block, invocation stop all. Actual native and injected cleanup tests. Gate 4L/5/6. |
| B10 | Single/multiple checks, prerequisites, changing resource observations, deadline consumed by prior checks/setup/cleanup, independent runs, no timeout, explicit retry as new invocation | One active owned native session per invocation, no hidden retry or budget reset, measured elapsed not fabricated resource use, fresh policy per check. No arbitrary cap or physical guarantee. Actual native trace + service tests; future parallel and cross-context budgets gated. Gate 4L/5. |

Regression carryover: check existing `project-binding-check-local-cleanup`,
`key-safety-prerequisites-block-dependent-checks`,
`aggregate-runtime-scan-preflight`,
`aggregate-runtime-capability-isolation`,
`aggregate-native-service-lifecycle`,
`aggregate-service-output-privacy`, `compiled-artifact-yaml-loader-diagnostics`,
`duckdb-owned-project-binding`, `local-adaptive-resource-targets`,
`duckdb-worker-process-lifecycle` (historic ID now native outcomes),
`duckdb-controlled-owned-session`, scratch/privacy rows and matching
index routes. No applicable pending capture row identified in reviewed files;
implementation must add/update reusable lifecycle regressions with real
test nodes and rerun capture metadata and branch-wide advisory. No
placeholder nodes or coverage claims.

### BDD acceptance scenarios

- Given configuration fails before engine setup, when run returns, then
  the invocation has an ID, timing and failure stage, no fake check results.
- Given compile completed yesterday and authored YAML changes today, when
  run consumes valid compiled inputs, then it executes the compiled plan,
  does not silently recompile or claim freshness.
- Given two checks share a prerequisite, when evaluating the plan, then
  it evaluates once, preserves dependency semantics and both result identities.
- Given a run has a 60-second timeout and setup plus first check uses 55
  seconds, when the next check starts, then only the remaining invocation
  budget is available; expiration stops later native work. Cleanup time
  is included even if total duration exceeds 60 seconds.
- Given an active native query receives a cancellation request, when native
  return and interrupt caller are still pending, then neither release nor
  successful completion is claimed; once stopped, close and clean safely.
- Given a native failure and later cleanup failure, when finalizing, then
  both are distinguishable, no comparison value is published and only
  affected database work is blocked unless the whole invocation is stopped.
- Given a caller repeats a failed invocation, then a fresh ID and bindings
  are used; Recon never automatically repeats a comparison.
- Given a process is externally killed, then no completed outcome is
  invented, no retained scratch is adopted, no unrelated state is deleted.

### Source and responsibility map

| Existing boundary | Owns / may change | Must not own |
| --- | --- | --- |
| `services/run.py`, private focused lifecycle/plan helper if justified | invocation ID/clocks, preparation, plan handoff, cancellation policy, finalization and command projection | SQL, native control math, duplicate engine/graph, artifact writer |
| `check_engine/engine.py`, prerequisites/models | one dependency evaluation/cache, typed plan consumption, outcome aggregation and explicit not-started reason | connection lifecycle, OS signals, CLI, publication |
| `services/_bound_runner.py`, private owned-session protocol | register active session with invocation controller, stop before native work, ensure cleanup and affected-context isolation | global scheduler, native SQL settings, unsafe cross-thread close |
| `adapters/duckdb/_bound_execution.py` | verified native interruption and call/close ordering; existing native policy/scratch ownership | invocation budgets, retry, host termination, new adapter API requirement |
| `services/results.py`, `cli/main.py` | existing command result/exit mapping; minimal optional invocation control and safe diagnostic wiring | raw result serialization, global library signal handler, generated files |
| Existing loader/config modules | preserve compiled input validation and current scoped config | implicit compile or new cache/freshness mechanism |

Possible private helper names are not design commitments. Extract only cohesive
ownership, not a generic framework. Preserve BaseAdapter API, all existing
supported operations and public serialized shapes; new timeout/cancellation
entrypoints and reason codes are additive proposed public changes, requiring
approval, strict validation and compatibility/changelog documentation at
implementation. No schema/version bump for artifacts not emitted here.

### Scoped gate dispositions and exit

- Gate 5: proposed ADR 0027 covers identity, explicit compile, lifecycle,
  existing statuses/exit mapping and typed metadata. Durable schema
  versioning/publication and final CLI semantics remain C1-C10.
- Gates 1A/4I/4P: preserve prerequisite/canonical binding, typed native
  placement and existing strict type proof (T7-T10 applicable; no type
  widening). T1-T6 retrofit remains M9.5, scope restoration M10.8 etc.
- Gate 4L/8C/P1-P6: R6-R8 invocation proof, all native pins and platform
  cases, no OS allowlist or hard physical guarantee; future adapter-specific
  proof and M8.3 publication retained.
- Gates 3F2/4J/6: safe messages and per-event diagnostic identity; no raw
  values or native exception payloads. Gate 5E: no artifact writes, existing
  owned current-check scratch only; M8.3 writer separate.
- Selector readiness: compiled scope distinguishable from actually executed
  work; no selector execution. Sink references absent, no external writes.
- Before implementation: explicit approval of proposal and any unresolved
  native control/API choices, validate public docs, ensure exact scope and
  compatibility alignment; any actual required proof not obtainable is a
  blocker, not a waiver. No gate globally closed.
- Definition of Done: all B1-B10 variants and BDD mapped to real test nodes,
  critical RED/GREEN, preserved A/R/P regressions and existing native suites,
  actual deadline/cancel/cleanup evidence for required pins/platforms, no
  false success or privacy drift, no new writes, review-fix on each slice
  and final cumulative branch; Ruff format/lint, mypy, full CI, native
  matrix, pre-commit and branch-wide regression capture advisory pass.
  Docs, compatibility/changelog, private continuity and future gates synced.
  Separate implementation and merge approval; no release or M8.3 work.

## Maintainer-approved direction and detailed interface contract (2026-11-27)

The maintainer approved the proposed direction above. This section refines
the interfaces and lifecycle semantics without changing the approved scope.
No runtime implementation or public support claim from prework alone.
Implementation authorization remains separate after validated prework
integration.

### Invocation interfaces and ownership

- CLI: `recon run --timeout-seconds 60` is an optional positive integer
  number of seconds; omission means no deadline. No environment variable
  or project/profile/contract configuration precedence is added. Invalid
  CLI syntax/value is a usage error; invalid embedded argument is a
  configuration error with sanitized diagnostics before project/native work.
- Embedded: `RunService.execute(*, timeout_seconds: int | None = None,
  cancel_event: threading.Event | None = None) -> ServiceResult`.
  The caller owns the Event; Recon never clears or mutates it. A pre-set
  event requests cancellation before preparation. No default deadline,
  new mandatory argument, callback registry or public adapter API.
  Reject bool and other non-integer timeout values, zero and negatives.
  Use integer monotonic nanosecond arithmetic; do not convert an arbitrary
  authored duration to an unbounded native/thread wait or hardcode a
  maximum workload duration. Wait in bounded observation intervals.
- Existing `ServiceResult` return fields, dictionary and non-run commands
  stay unchanged. A private run-specific invocation envelope behind
  `RunService.execute` owns the typed plan, optional finalized internal
  `RunResult`, invocation lifecycle status, stage, safe diagnostics and
  command projection; later publication consumes this same envelope,
  not a second run or raw dataclass serialization. Early failures have
  identity/timing even before a valid plan exists. Unknown project/scope
  is absent. No generated artifacts or new stable serialization here.
- Generate `run-{uuid4().hex}` at invocation entry. Record precise UTC
  labels and monotonic elapsed time at one invocation finalization boundary
  after native/session cleanup and control-thread join. Duration is not
  derived from wall clock or summed across checks. Clock correction or
  suspend semantics cannot be presented as hard wall-clock termination.
- Existing exported `CheckEngine.run` accepts its historical
  `finished_at` keyword for callers supplying an already known label;
  extend the private engine injection contract to allow an unset
  `finished_at` (None), and compute the engine-end label after evaluation
  when unset. RunService must not fabricate a future timestamp. Its
  authoritative finalized envelope records the invocation-end label
  after cleanup; preserve legacy direct engine explicit-value use and
  existing test injection without a second execution path or exception-
  driven signature fallback. This pre-alpha injected engine seam is not a
  promise of native cancellation support for arbitrary custom engines;
  an explicit required control cannot silently be ignored. Use the same
  cooperative context contract or report affected unsupported control.
- Freeze the loaded plan identity/order/dependency and whole compiled
  scope, use the existing index/cache and loader uniqueness/matching
  checks. Do not reparse authored YAML, re-read a different artifact
  mid-run, imply authored-source freshness, or build another graph engine.
  Plan/capability/admission facts describe actual known stages, not a
  claim that every planned check ran. Preserve known blocked decisions.

### Stop, result and cleanup semantics

- First observed stop cause is latched invocation-locally; if deadline
  and caller signal are first observed together, explicit cancellation
  wins deterministically. Preserve distinct already-recorded failures;
  no inference of real-world event ordering. Check at preparation/plan
  boundaries, dependency resolution and before each native data statement
  and subsequent fetch/verification; no new work after observed stop.
  Blocking setup calls without a safe native interrupt are cooperative
  checkpoints, not hard time limits. No timeout reset per check.
- Proposed additive non-execution reasons are `run_cancelled` and
  `run_deadline_exceeded` under existing `not_executable` status, with
  distinct safe diagnostics `RC_RUNTIME_RUN_CANCELLED` and
  `RC_RUNTIME_RUN_DEADLINE_EXCEEDED`. Unstarted planned checks get the
  invocation stop reason, not `selected_out` or a fabricated prerequisite
  blocker. An interrupted attempted check with no trustworthy completed
  comparison is `error` without value payload, with stop and actual
  cleanup/native diagnostics. Preserve earlier finalized results and
  valid completed evaluation only after confirmed cleanup. Record attempt
  separately from the existing executed/completed-result flag.
- Existing aggregate check-status precedence remains unchanged. A stopped
  or failed invocation has a distinct lifecycle failure/stop reason,
  never successful or a fabricated `no_checks` aggregate. Command exit
  for runtime stop is 3, even if a preceding check passed/failed; earlier
  independent configuration/validation failure retains its truthful
  primary category. Invalid CLI usage uses the existing usage exit 2;
  invalid embedded operational arguments use configuration exit 4.
  Finalization seals a single outcome: stop observed before sealing
  cannot become success, a later event cannot rewrite a returned result.
- Cancellation during rollback/close does not interrupt cleanup.
  Preserve primary and cleanup failure, retain uncertain scratch and
  affected-database isolation, no forced close or recovery. Completion
  may exceed the timeout; process kill cannot return a trustworthy result.
- Native stop coordination is one invocation-local control owner, with
  an active-call lease managed by the adapter around actual interruptible
  execution/fetch spans. Register before a native call, recheck stop
  immediately before entering, and recheck after return before accepting
  result. An interrupt before native launch is not proof; while stop is
  latched and the same call is still in flight, a bounded observation
  cadence may repeat the existing native interrupt request until call
  returns. Do not retry the query. No interrupt of a different session,
  idle/cleanup call, or next invocation. No lock held across native work;
  unregister and join any borrowed interrupt caller before rollback,
  close or scratch cleanup. The private session protocol may expose the
  already-existing interrupt capability; public BaseAdapter is unchanged.
  Verify actual active-spill interrupt and close in production integration,
  not only a mocked thread or returned interrupt call.
- CLI must remain responsive to delivered SIGINT while native code runs.
  Use the ordinary synchronous RunService/CheckEngine execution once on a
  joined in-process execution thread, with the CLI main thread coordinating
  signals (one native owner, not a worker process or parallel executor).
  A scoped main-thread SIGINT handler records only a simple stop latch;
  ordinary coordinator code transfers that request, never closes native
  handles or runs native work in a signal handler. Restore prior handler
  on all paths; respect ignored/unavailable signal delivery. Embedded
  calls stay synchronous on the caller's thread and never install signal
  handlers; an invocation-local observer is needed only when explicit
  cancellation/deadline is requested. Share one stop-control implementation
  rather than separate CLI/embedded runners. No detached/daemon runtime
  threads, cross-process IPC, OS-specific production console manipulation,
  global scheduler or forced process termination. Do not claim control
  of a signal that the host never delivers. Explicit timeout and caller
  Event remain independent of CLI signal delivery.

### Cumulative envelope and typed evidence

Keep exactly one active native check per invocation, even through dependency
recursion, and freshly resolve resource observations for each owned session.
Different independent invocations are not globally serialized; no
process-wide resource reservation. Track exact planned/attempted/finalized
check counts and native-call attempts, elapsed time and peak concurrent
owned native work; distinguish attempts from data scans or comparison
completion. Shared explicit deadline budgets the invocation. Managed
memory/thread/spill settings are per-session controls, not actual bytes
consumed or additive cumulative use. Do not sum capacities or optional
catalog row estimates as actual scans. Where scope-correct cumulative
actual scan/CPU/disk/transport/cost evidence is not available, retain
explicit unavailable provenance; no invented cap. Additional engine-specific
cumulative control/measurement and multi-context budgets remain mandatory
at the native adapter, scope expansion and conformance checkpoints in the
resource assignment (R1/R7/R8, M12.5/M13.5/M29 and integration gates).
No new blanket limit, workload cap or run-wide physical guarantee.

Preserve evidence at its owner: configuration resolver records per-setting
authored scope/mode where known (including reset); existing native adapter
records requested/adjusted target, verified effective readback/availability
and binding/placement outcomes without path, raw host facts or query text.
The current code discards `_apply_native_controls` readback and only emits
advisories from adaptive target calculation; preserve typed safe facts at
those seams, not by re-observing, recomputing or reverse-parsing diagnostics.
Do not duplicate policy precedence or native control math. Final actual
admission must not be conflated with preliminary scan-budget classification.
Use allowlisted per-check metadata for capability/placement/admission,
policy mode/origin, control effect/unknown state and advisory codes;
keep sensitive identifiers, data, raw plans and credentials private.
C10 owns public field allowlist/versioned publication, not rerunning a check.
No public resource settings change or new type/scope capability.

### Additional required proof before exit

Extend B1-B10 with simultaneous stop/deadline, preset/reused caller Event,
invalid arguments, very large valid integer duration (no wait overflow),
wall-clock rollback, direct legacy engine interface, unknown injected
control, before/after dependency, before launch/execute/fetch/verification,
between statements, during cleanup, cancellation after final seal, repeated
interrupt lease and deregistration, exception-raising interrupt, actual
SIGINT and restored prior handler, non-main embedded invocation, no runtime
daemon/thread leak, and unchanged unrelated connection/invocation.
Test no more native reads after observed stop and no release while interrupt
or executing call remains live. Test one actual plan evaluated once, matching
loader inputs, distinct stage outcome and unchanged ServiceResult dictionary.
Verify safe typed native readback/availability and no false actual-resource
totals or raw metadata. All required standard/pinned/platform and production
path evidence remains mandatory; a synthetic feasibility probe is not
implementation conformance. Windows host-disabled Ctrl+C is not an engine
failure or a promise of signal delivery. No OS-version allowlist.

### Native stop feasibility evidence (synthetic, not production integration)

Pinned Core baseline 40e756209b80a267674f7376c6bd4db81c6a7214. Temporary
probe changes were limited to the workflow and synthetic script; product
tree unchanged. [Initial probe](https://github.com/recon-labs/recon-core/actions/runs/46031265268)
failed before executing SQL because the checkout was shallow. Corrected
[probe](https://github.com/recon-labs/recon-core/actions/runs/46031361731)
at 7308834d2d4f69d657420d251779936c2e0b9cc6, 7/8 completed successful lanes
; macOS 26 / 1.4.5 remained queued at the checkpoint.
Actual successful lanes include all four supported pins on Linux, macOS 15
with 1.0.0, Windows 2022 with 1.0.0 and Windows 2025 with 1.4.5.
Each completed lane demonstrated interruption of a synthetic active query,
repeated interruption across a deliberately forced pre-launch gap, joined
execution/control calls and an unchanged operational unrelated connection.
POSIX cases delivered actual SIGINT to the isolated CLI-style process;
the initial Windows cases used Python-level signal delivery only.

The [first isolated Windows console probe](https://github.com/recon-labs/recon-core/actions/runs/46031594402)
at 97a87f9e39f4a516d40d9271dcbc82421d9a034b generated isolated console
events but failed to confirm native return; do not count as success.
The [corrected isolated fixture](https://github.com/recon-labs/recon-core/actions/runs/46031801850)
at b3f9704b93157609ee879830cd80e88c3ba945ec passed both Windows lanes,
jobs 140617206076 and 140617205601. The fixture enabled normal Ctrl+C
processing only in its isolated child, verified exact console membership
before generating an actual console event, recorded the handler request,
confirmed the native interruption and joined the owner before returning.
No production console manipulation is proposed. A host which suppresses
signal delivery remains outside a delivered-signal cancellation guarantee.
The native timeout and embedded Event paths do not depend on Ctrl+C.

The test workload and wait intervals are bounded experimental inputs,
not runtime defaults, workload caps or a cancellation latency SLA.
Prior native active-spill interruption/binding/cleanup evidence remains
the M8.1.2 prerequisite. These independent probes justify the selected
portable coordination direction, not the implementation of the actual
RunService deadline, signal path, fetch/cleanup races or safe metadata.
All B1-B10 production-path and platform proofs remain mandatory, including
macOS 26 if its required lane is available, equivalent evidence or recorded
blocker under P1-P6 otherwise. The temporary branch refs were restored
to the exact baseline; experiment files are absent from mergeable trees.
No release, global gate closure or runtime implementation approval.
