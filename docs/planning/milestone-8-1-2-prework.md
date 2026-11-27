# Milestone 8.1.2 - Adaptive Local Resource Policy And Admission

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

### Implementation step 1: candidate disposition and test-first order

Compared approved design head against main: 51 changed files, including dependency, source, test and documentation paths (see exact Git
compare; use actual path inventory for routing). Candidate implementation remains parked until each replacement
slice is ready. No history rewrite.

| Candidate source/test family | Approved implementation action and proof |
| --- | --- |
| config/_local_resource_policy.py, config/project_config.py, tests/config/test_project_config.py; existing profile selection/rendering/model seams | Replace unreleased scan-budget.local and reserve leaves with the six logical adapter-scoped settings and one resolver; preserve old public project/profile behaviors, strict typed literals, duplicates, secret-safe diagnostics, selected target/reference behavior, atomic precedence/reset, identity invariance and same-context conflict refusal. Tests first. |
| check_engine/scan_budget.py, tests/check_engine/test_local_resource_targets.py | Preserve existing admission APIs and current footprint guard; replace historical reserve formulas with approved automatic/percent/fixed calculation and unknown/zero behavior. Move engine-specific arithmetic to private DuckDB owner as necessary; preserve one policy resolver. Test changing capacity, explicit bounds, native rounding, scratch shared headroom; no interim cap removal here. |
| adapters/_local_resource_observation.py and _portable_resource_observation.py plus matching tests | Replace exhaustive cgroup hierarchy/Windows job/mount instrumentation with trustworthy independent optional facts, minimal verified cgroup-v2 scope and native recommendations. Retain missing/zero/partial/malformed/denied evidence, constrained scope, actual native behavior; not blanket unlimited. |
| adapters/duckdb/_native_resource_controls.py and native control tests | Reuse verified native control and readback helpers where suitable; preserve actual spill effect, failed control refusal, settings isolation, startup vs post-open distinction. |
| adapters/duckdb/_bound_execution.py, test_duckdb_bound_execution.py and test_duckdb_adapter.py | Preserve exact binding, bounded fetchmany(2) count reader, exact domains, existing public adapter compatibility; replace control session path with guarded native actor and actual close/interrupt/noninterference proof. Do not weaken M8.1.1 or M7.4. |
| adapters/duckdb/_resource_worker.py, _worker_bound_session.py, _worker_control_protocol.py, _worker_result_codec.py plus matching candidate tests | Retire subprocess/IPC/codec/proxy/replay/EOF watchdog mechanism after approved native replacement proof. Retain exact native numeric/shape bounds, binding/lease, cancel requested vs confirmed, errors and L1/noninterference. No worker crash-containment claim. |
| adapters/_resource_scratch.py, _scratch_filesystem.py, _scratch_namespace.py, _windows_scratch_security.py plus matching candidate tests | Replace stable namespace/tickets/leases/restart recovery and exhaustive mount/ACL checks with unique private per-check scratch and minimal actual native privacy mechanism; retain no-delete-unowned/replaced/live, actual ACL inheritance, cleanup/failure, abrupt residue retained and fresh invocation independent. Reuse only proven needed primitives. |
| pyproject.toml | Review optional psutil extra against minimal observation; no mandatory Core dependency. |
| regression capture metadata and index | Retain all main rows. Preserve historical candidate nodes until each replacement is implemented and verified. Update applicable capture rows and markers to actual new nodes, reroute changed/deleted paths, record retired mechanism rationale and carryover; do not claim proof before GREEN. |

The existing A/R/B/P and capture-ID disposition table below is approved
subject to these scoped replacement proofs. Specific obsolete IPC framing,
persistent recovery and exhaustive OS-certification cases may retire;
all applicable correctness, privacy, required-control, noninterference,
cancellation and cleanup outcomes must be tested. Preserve exact historical
nodes in prior commit and private evidence. No regression row silently
deleted or marked satisfied. First slice: tests for project/target/connection
schema, strict validation and precedence plus pure target calculations,
then smallest conformant implementation. Critical negative assertions
require observed RED before GREEN; ordinary test-first cases may use source
review when local validation unavailable. Existing standard CI first;
persistent native/platform proof and Windows live-WAL fixture remain
mandatory. No code changed in this authorization/inventory step.

## Implementation-level calibration evidence and open decision (2026-11-27)

The initial measured project-runtime experiment [46015981225](https://github.com/recon-labs/recon-core/actions/runs/46015981225)
at temporary harness commit `d0f36afcc4f5eeededdf43da56214a0e02c82c4f`
completed 24 synthetic cases, all four pinned engines (1.0.0, 1.3.2,
1.4.5, 2.0.1). An approximately 770 MiB database completed in a real
512 MiB/2-CPU cgroup with 128 MiB/one-thread controls and actual spill
(66-155 MB sampled). Auto memory with one authored thread, 75% memory
with one thread and a capable 2 GiB environment also completed; small
compressed wide-key workloads were materially costlier. A real 64 MiB
ext4 loopback with approximately 53.8 MB free gave controlled native
query errors on all four pins. Successful/controlled error cases preserved
the unrelated observer, database bytes/metadata and confirmed owned cleanup.
Sampler cleanup races in this initial harness prevent an exact peak claim.

The full automatic-thread experiment [46016305450](https://github.com/recon-labs/recon-core/actions/runs/46016305450)
exposed abrupt termination in tight environments. Isolated case rerun
[46016574334](https://github.com/recon-labs/recon-core/actions/runs/46016574334)
at `c01631c9793037e4f5d22f4308db39dd8e47f8cf` confirms OS OOMKilled=true,
exit 137, not a controlled Recon error. With 512 MiB/2 CPU, the approved
50% automatic memory/native-bounded threads passed six of eight repeated
large narrow cases; 1.3.2 and 1.4.5 each terminated one invocation.
One-thread auto and 25%-memory/one-thread alternatives passed the large
narrow fixture on all four pins; 25%/two-thread and fixed 128 MiB/two-thread
alternatives caused native errors on 1.3.2 and 1.4.5. All four capable
2 GiB/4 CPU cases passed; 75%/auto threads passed on this rerun but earlier
1.4.5 terminated. The approximately 104 MiB compressed wide-key workload
with fixed 128 MiB/one thread still caused a kernel OOM on 1.0.0 in the
rerun; other pins returned controlled error or PASS. Actual tmpfs tests
verified shared headroom targets and advisories, but 1.4.5 still suffered
kernel OOM at automatic settings; the 25% variant gave controlled error
on 1.3.2 and 1.4.5 and PASS on the other two pins. Native-managed memory
and spill ceilings are not total process/cgroup memory guarantees.

No calibration conclusion based on failed-job counts alone: the detailed
outcomes above distinguish real native errors, kernel kill, successful
comparison and test-harness failures. No false success, no claim of cleanup
after OS kill, no change to approved defaults, no automatic retry, no
new size/memory-per-thread cap, no reintroduction of worker/watchdog.
The temporary harness was removed from its experiment branch at
`c6660b078355c8db7adaf3a1f0ac9a4d5e8ff772`; exact historical reproducibility
and CI evidence remain. Permanent captured per-check, native spill,
interruption, error, cleanup and abandoned-residue tests remain.

**Step 7B focused reassessment approved (2026-11-27):** The maintainer
authorizes measured improvement of automatic memory/thread selection
and explicit best-effort limitations with actionable advice. Keep authored
fixed/percentage memory, explicit thread settings, precedence, spill
scope and the native-first architecture unchanged. Compare baseline to
DuckDB-specific automatic thread selection using its published memory
per thread guidance (https://duckdb.org/docs/current/guides/performance/environment).
The documented 125 decimal MB/thread rule of thumb and 1 GB/thread
lower edge of ideal performance guidance are candidate tuning inputs,
not workload admission floors, physical guarantees or cross-adapter
requirements. Retain at least one thread for otherwise usable native
execution; do not raise zero capacity, introduce a hardcoded database
threshold, retry automatically, or force one thread on capable machines.
Evaluate repeated actual narrow/wide, constrained/capable and tmpfs
cases, including OS-killed cases as distinct from native errors. Adopt
only a measured improvement with transparent remaining limits.

### Focused tuning reassessment: measured implementation evidence

Candidate-only experiment [46020054117](https://github.com/recon-labs/recon-core/actions/runs/46020054117)
at `abd6fda3cce028378218b08dfe7b34ed5e7b4b91`, four pins and three
repetitions per candidate/workload (144 cases), compares original auto
parallelism to 125 MB and 1 GB per managed-memory thread candidates.
At 512 MiB, large disk cases improved from 9/12 PASS (three kernel OOM)
to 12/12; tmpfs from 6/12 PASS (three native ERROR, three kernel OOM) to
12/12. Small costly wide-key cases: original 5 PASS/6 ERROR/1 OOM;
both candidates 4 PASS/6 ERROR/2 OOM. At 2 GiB/4 CPU all three 12/12
PASS, but 1 GB guidance restricts to one thread and is about 2-3 times
slower than the four-thread candidate. Thus choose the less restrictive
125 decimal MB/thread native guidance, not a workload admission floor.
No claim that every workload benefits.

Implemented at `42f0a3995a303dcfa37c4f9a678d5d5418381558` after eight
intended test-first RED failures at `e52e955d3509e995fb7a7fe762eaac5e9e67fb61`
(CI 46020552334 native 3.11 job 140578775121). For automatic threads,
when observed headroom and the positive managed target are known, reduce
the existing positive CPU/native thread target to at most
max(1, floor(managed-memory-bytes / 125000000)). No invented thread count
from absent CPU/native evidence; exhausted capacity unchanged. The
50%/90% memory/spill ratios and explicit fixed/percentage memory/spill
and authored threads semantics are unchanged. Existing CLI and embedded
warnings explain reduction, total process memory uncertainty and
supported tuning. Standard CI 46020772943 10/10 GREEN and native platform
CI 46020772995 9/9 GREEN on exact implementation revision.

Actual production calibration [46020823693](https://github.com/recon-labs/recon-core/actions/runs/46020823693),
temporary harness `19461dc119c941d6106aabb13b3448e8da33cf4b` based on
that revision (no calculation monkeypatch), all four pins, 64 cases:

| Workload / configuration | PASS | Native ERROR | OS OOM kill |
| --- | ---: | ---: | ---: |
| 512 MiB, large narrow, auto disk | 12 | 0 | 0 |
| 512 MiB, large narrow, auto tmpfs | 12 | 0 | 0 |
| 2 GiB / four CPUs, large narrow, auto | 12 | 0 | 0 |
| 512 MiB, small wide, auto disk | 3 | 6 | 3 |
| 512 MiB, large, fixed 128 MiB/one thread | 4 | 0 | 0 |
| 512 MiB, large, explicit 75% memory | 3 | 0 | 1 |
| 512 MiB, large, explicit one thread/auto memory | 4 | 0 | 0 |
| 512 MiB, large, actual low free disk | 0 | 4 | 0 |

All 60 returned outcomes verified confirmed release, independent observer,
unchanged database and empty current scratch; no harness assertion failures.
Four kernel OOM kills (1.0.0 one small wide; 2.0.1 two small wide; 1.4.5
explicit 75%) returned no result, so no cleanup claim. Large automatic
cases selected one thread at 512 MiB and four at 2 GiB across all pins.
Actual fixed spill sampled 70-157 MB and low disk produced controlled
native errors across all four. Actual memory-backed capacity calculation
and actionable advisories verified. Both temporary harnesses removed
(a882c4c5a3445c44c049d62cc5c5aaebddc5076d and
41ca23f815655566194765994e052e69192e2c37); immutable evidence retained.

Additional memory-fraction comparison [46021219113](https://github.com/recon-labs/recon-core/actions/runs/46021219113)
at test-only commit `98397a0ce3196a45a972b065526ce3a3a805dfd8`:
120 cases, four pins, three repetitions per configuration/workload.
Both candidates use the same 125 MB/thread guidance; compare the current
50% automatic memory target with a 25% alternative. Actual observations
and real project query execution were retained; only the candidate
calculation was varied. No harness assertion failures.

| Workload | 50% PASS / ERROR / OOM | 25% PASS / ERROR / OOM |
| --- | --- | --- |
| 512 MiB large disk | 12 / 0 / 0 | 12 / 0 / 0 |
| 512 MiB large tmpfs | 12 / 0 / 0 | 12 / 0 / 0 |
| 512 MiB small wide | 6 / 6 / 0 | 3 / 8 / 1 |
| 1 GiB small wide, four CPUs | 6 / 6 / 0 | 6 / 6 / 0 |
| 2 GiB large, four CPUs | 12 / 0 / 0 | 12 / 0 / 0 |
| Total | 48 / 12 / 0 | 45 / 14 / 1 |

The 25% alternative does not improve overall measured outcomes; at 1 GiB
it also reduces automatic threads from four to two without improving
pass counts. Retain the approved 50% starting heuristic and measured
memory-aware threads. This run does not erase earlier observed OOM kills
or establish universal safety. All 119 returned outcomes confirmed
release, observer isolation, unchanged database and scratch cleanup.
The one kernel OOM kill occurred on DuckDB 1.0.0 at 25%/512 MiB, small
wide workload. Temporary harness removed at
`87ad598db57338e777f9ddaf5d4d7c98cd6b2e2c`.

Step 7B measured improvement and best-effort limitations meet the approved
focused reassessment: retain the modest native-specific automatic heuristic,
not a hard quota, retry, worker, or new workload restriction. Document
wide-key and authored high-memory risks, lower thread/memory settings and
external memory capacity as operator options, not promises. Future
native/default/workload/deployment changes recheck measured outcomes
under Gate 4L and existing A/R/P assignments; M8.2 invocation termination
responsibilities and M29 candidate conformance remain open. Final
cumulative review and exact final validation still mandatory; no merge
or release approval implied.

**Historical open Step 7B calibration decision (superseded by focused
reassessment approval):** do not close the gate or claim
universal safe automatic tuning. The observed tradeoff needs explicit
maintainer acceptance of the approved best-effort defaults with documented
limits, or approval of a revised adapter-specific tuning rule followed by
measured recalibration. Lowering only memory or setting one thread
universally is not a proven fix. Existing M8.2 invocation lifecycle,
M10.8 readiness/scope, M29 and future candidate gates retain the measured
resource and abrupt-exit outcomes; repeat the constrained/capable
native workloads on default/control/dependency changes and before
promotion. Independent 7C/7D evidence may proceed; no release, merge
or completed-gate claim.

## Current status: whole design reopened (2026-11-27)

Historical suspension record; superseded by the current authorization above.

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

## Consolidated native-first replacement design (proposed for approval, 2026-11-27)

This is the proposed detailed replacement, superseding the earlier provisional
architecture and tuning proposals below only if approved. Current code remains
suspended. Both standalone and embedded usage are mandatory in M8.1.2.
Split Decision: Already Split / Follow Existing Split.

### Selected architecture proposal

Use the same guarded native DuckDB path for both CLI and embedded project runs.
No process-mode detection, public API change, separate check worker or IPC.
For each admitted check, the existing owned session holds its ordinary
read-only connection for the exact approved file (native writer exclusion).
A separate native memory instance with its own native resource settings
attaches that file read-only, selects the actual native catalog and owns
the existing read transaction, typed reads and lease. No database copy or
new user-facing attachment support. Native catalog name must match the
original direct connection; no suffix or filename heuristic. For the
native initial memory catalog collision only, use the tested native
ATTACH temporary seed / USE / DETACH / attach original / USE / DETACH seed
sequence. Verify the actual catalog list, file, table scope and native
read-only property before data queries, no extra user catalog, views, temp
shadow, external relation or other existing unsupported scope. Keep
original path/sidecar/lease and result domain protections; never execute
untrusted SQL. Test native naming collision and quoted identifiers, actual
transaction, repeated check close/reopen and failure boundaries. Do not
assume arbitrary new DuckDB versions work without proof, or reject solely
on version label.

Retain original handle until actor stop and close confirmed. Close actor
first, then guard, then owned scratch; try applicable cleanup on every
setup/execute failure, preserve primary and cleanup error, do not release
protection or delete live scratch if actor close unconfirmed. Keep L1 latch
for subsequent affected work. Native interrupt only on owned actor; no kill
of process or unrelated connection. Distinguish cancel requested/confirmed,
failed/native error and exact comparison result. Full invocation Ctrl-C,
deadlines, retries and scheduling remain M8.2; prove any cancellation used
by M8.1.2, including actual active-spill interrupt and cleanup, before exit.
A native crash or OS OOM can terminate the shared application or CLI.
No hard process-memory, CPU, disk quota, crash containment or guaranteed
completion claim. External orchestration may provide those controls.

A normal compatible same-file reader remains unchanged; simultaneous
independent checks/invocations are not globally reserved or scheduled.
Existing DuckDB refusal when an already open same-file reader uses a
different startup configuration remains the existing binding limitation,
not a new deliberate restriction. Return sanitized scoped connection error
and advice to close conflicting connection if appropriate or run Recon in
a separate ordinary invocation; no automatic alternate mode or native
global mutation. Do not introduce a new borrowed-connection API or require
callers to authorize arbitrary changes. This limitation is explicitly
proposed for retention, not an unaddressed embedded milestone deferral.
Preserve injected loaders, engine, registry and environ, existing API and
CLI semantics. If future evidence disproves the two-handle equivalence,
reopen design, do not silently drop guard or restore custom workers.

Rationale: actual ordinary direct CLI proof 45917130110, guarded embedded
native proof 45920605605 (616 selected existing + 64 focused tests),
both 1.0.0 actual spill cases 45920361925 and six newer-pin actual spill
cases 45920605605; all four pins exact outcomes with unchanged observer.
The independent unguarded alternative failed writer protection; the guard
corrects it. One path avoids two implementations and context guessing.
The Windows baseline WAL fixture failure remains an explicit coverage gap,
not a passed test. Repair the synthetic fixture with portable equivalent
actual sidecar proof without weakening the regression and verify on both
Windows releases and existing Linux/macOS lanes.

### Exact proposed policy and configuration

Configuration placement and precedence are reopened by maintainer request
(2026-11-27); this replacement is a proposal, not implementation approval.
The previously approved automatic/percentage/fixed tuning modes remain.
No released configuration migration: the prior execution.scan-budget.local
and its candidate leaves were never released. Do not implement a deprecated
alias or two configuration loaders for them.

Use the existing project file recon_project.yml (config-version 1) and
connections/profiles.yml selected profile/target. Keep execution policy
separate from connection identity, authentication/credentials, contract
comparison semantics, and native factory connection payloads. Reserve
execution for operational policy; no generic public controls are introduced
until their semantics are independently agreed. The only implemented adapter
policy in this milestone is DuckDB.

Project-wide adapter defaults (optional):

```yaml
execution:
  adapters:
    duckdb:
      managed-memory:
        percent: 75
      spill:
        percent: 80
```

In connections/profiles.yml, the existing selected target may carry adapter
defaults and connection-specific exceptions in a sibling execution mapping,
not inside the connection payload:

```yaml
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: data/example.duckdb
          warehouse:
            type: duckdb
            database: data/example.duckdb
        execution:
          adapters:
            duckdb:
              managed-memory:
                mib: 2048
          connections:
            legacy:
              managed-memory: auto
            warehouse:
              managed-memory: auto
```

Resolve independently by logical setting in ascending precedence: native/
adapter automatic defaults -> project defaults for literal adapter type ->
selected target defaults for that type -> selected target named connection
override. No extra profile/environment selection or environment-specific
file discovery. A setting replaces the complete logical setting, not a
deep merge of mode members. Omitted means inherit; explicit auto resets
memory, spill, threads or scratch to adapter automatic; explicit none resets
optional max-database-mib and warn-estimated-input-rows to absent. Empty
outer maps inherit; empty mode maps, null, duplicate/unknown fields or
conflicting mode members are invalid. No project/target hard security
ceilings are implied by these overridable defaults; native/operator limits
still apply. Future hard admin limits must be separate non-bypassable policy,
not another override of tuning defaults.

DuckDB has six logical settings: managed-memory and spill (literal auto or
mapping with exactly one of percent or mib), threads (auto or positive int),
scratch-directory (auto or nonempty path), max-database-mib and
warn-estimated-input-rows (none or positive int). Percent is strict YAML
integer 1..100; MiB and other integers are positive within checked signed
64-bit/native domains; bool/float/quoted numeric/null invalid. Resolve
authored scratch paths relative to the project root unless absolute,
existing directory only, no implicit expansion, parent creation or alternate
base. Scratch auto uses verified standard temp base. No implicit environment
string-to-integer conversion or new templating: operational values are
typed literals initially; existing credential env_var rendering unchanged.
Selected target provides deployment overrides today; M28 owns any new
typed env/CLI override design and precedence proof. No contract/check/package
override, new target-selection CLI, new config version or new adapter API.

Core validates project/selected-target envelope; the DuckDB-specific schema
and arithmetic have a private adapter-specific owner, not generic engine
branches scattered across Core. Reuse one resolver for precedence and
separate selected execution settings from rendered connection
payloads, and resolves immutable authored policy once per referenced
connection/context; adapter owns native controls/calculations and fresh
capacity facts. Current supported adapter policy namespace is duckdb; unregistered
namespace in authored project or selected target defaults is a configuration
error, not silently ignored. Selected target connection override keys must
name a declared connection; validate values only for referenced connections
against their literal adapter type. Unselected target execution settings
are not loaded/validated beyond existing YAML document rules. Plain parse/
compile must not require profiles or native engine, and existing adapter-aware
compile behavior, injected loaders/registry/environ and public model
signatures remain compatible. Validate applicable runtime policy before data
reads; do not make rendering require capacity probes or open connections
just to validate tuning. Do not pass policy data through factory config,
native DSNs, SQL or adapter identity. Preserve existing connection-config
equality, same-file binding and redaction. A check using two connection
aliases in the same supported execution context must have identical
normalized effective authored policy (including reset/default and resolved
scratch path semantics); conflict blocks the affected check before data
reads with actionable sanitized advice to align settings. No choosing the
first/last alias, implicit policy merge, duplicate query or new cross-context
execution. Separate checks may use different policies serially, with fresh
native actor settings. M13.5 owns cross-context multi-resource policy and
placement, including independent remote/client scopes.

Propose removal of the two unreleased reserve leaves and continuous pressure
monitor, mandatory recovery, and the old project-local config parser shape;
preserve native control outcomes and existing public compatibility.

No default database size or estimated rows ceiling, for either usage path.
An explicit footprint maximum applies independently to all nine checks;
actual bytes below/equal pass, above refuse before data reads. No estimate
used to override required binding. Optional role-summed catalog estimates
only; missing/invalid estimate is unknown, no data scan to estimate,
no fabricated warning/zero. Warn above authored threshold without changing
result or execution. Preserve row-count reason specificity and canonical
matched admission; no hidden sampling, SQL rewrite, retry or timeout.
Existing 64 MiB guard remains until equivalent replacement proven on both
paths, not an alternative runtime mode after exit.

Automatic tuning is best effort, based on freshly observed resources
before each check; never a guarantee of availability under concurrent load.
Use integer bytes and native units; no arbitrary MiB floor. Optional
maintained psutil host available memory and process CPU affinity when
available (reuse optional DuckDB-extra dependency, no mandatory Core
dependency; import/probe failure advisory), stdlib disk_usage on selected
scratch. Native recommended memory/threads read from isolated native
instance; use conservative lower edge of rounded native display for a
computed ceiling. Linux simple verified cgroup-v2 fact only: read process
membership and actual mount mapping, accept memory.max/current and cpu.max
for an unambiguously matched visible controller scope, distinguish finite,
unlimited and unavailable; no exhaustive ancestor traversal, v1 parser,
namespace/host certification or Windows job/processor-group introspection.
A visible scope is not proof of all ancestors; mark incomplete scope as
unknown rather than infinite. If matching cannot be established, omit
that hint and advise when material. No hardcoded OS version gate.
Keep valid independent facts even when another probe fails.

H = minimum of available trustworthy positive/zero host and applicable
finite visible headroom observations (max-current saturated at zero).
No valid observation -> H unknown; preserve native recommendations and
warn about material missing scope. Proposed default memory M = min(native
recommended managed target if known, floor(H/2)) when H known; omit
unknown native recommendation from the minimum if native control support
otherwise established. H unknown -> retain native recommendation if valid
and warn; if no valid recommendation, leave native automatic setting only
when actual native execution/private spill protection is independently
verified, warn inability to tune. Authored fixed memory target replaces the
50% heuristic/native recommendation, capped by known finite H when
applicable; emit safe adjustment advisory if lowered. Authored percentage
p replaces both the default heuristic and native recommendation:
M = floor(H*p/100), using trustworthy available headroom, not total RAM.
If H is unavailable, refuse affected setup before data reads with sanitized
advice to use automatic mode or fixed MiB; never silently substitute 50%,
native defaults or total RAM. Partial trustworthy facts may be used with
material incomplete-scope advisory. Do not promise
effective physical limit. Known zero or target below supported positive
native resolution must not be rounded up; report unusable resource
condition before affected data work (no arbitrary small workload cap).
The default 50% is an adapter-local adjustable starting heuristic, not
universal safety rule. DuckDB documents managed memory exclusions and
50-60% total-memory guidance for OS OOM; this design uses available
headroom rather than total. Probe 45920824959: 20/20 exact successes for
50%/75% and explicit one-thread alternatives; 75% faster on tested wide
cases, 50% leaves greater margin for non-managed allocations and shared
usage. Choose 50% initially, explicit fixed or percentage override not
restricted to 50%; higher percentages trade headroom for potential throughput.
Final implementation-level calibration includes native recommendation
clamp (not applied in experiment), constrained/capable and changing load,
larger CPU machines, small costly versus large narrow, actual spill and
unknown evidence. Do not claim 50% or 75% proves safe everywhere.

C = minimum of independently trustworthy available CPU affinity/count,
visible positive finite quota/period where known and native recommendation
for automatic thread target. Round positive fractional CPU quota up to
an executable thread count; retain fractional quota as observation, not
CPU guarantee. Explicit threads replaces native default, bounded by known
available CPU capacity where meaningful; positive integer, native range,
warn if adjusted. Missing CPU hint retains native/explicit setting and
advises when material. No default fixed thread count or memory-per-thread
restriction. Do not infer CPU quota from installed cores alone.

F = actual available bytes at selected scratch directory from disk_usage.
Default spill target S = floor(9*F/10), using DuckDB's documented native
90% disk convention, not universal quota. Explicit fixed spill replaces heuristic
and is capped by known available F, warn if lowered; no physical reserve
guarantee. Authored percentage q uses S = floor(F*q/100), not total disk.
F unknown -> use verified native automatic spill mechanism where supported,
warn missing disk observation; explicit supported fixed target still applies.
Explicit spill percentage with unknown F refuses affected setup with actionable
advice to use automatic/fixed MiB or an observable scratch base. No silent
substitution; unknown free bytes is not unlimited. Known
no usable positive spill target: use native no-spill only if exact effect
verified and emit warning, otherwise affected resource setup error; no
silent alternate directory, no fabricated minimum. A known memory-backed
scratch is not independent disk capacity: account for trustworthy shared
memory headroom where available, otherwise advise uncertainty and recommend
disk-backed scratch, do not count unknown as physical disk assurance.
Unknown filesystem type is not by itself refusal. No mandatory filesystem
classification or global reservation. Native spill setting applied after
open, before query, because startup readback can be ineffective. Required
explicit or safety-dependent control must actually work at promised scope;
if unavailable, verified equivalent or affected refusal, not a silently
ignored ceiling. Automatic optional tuning missing -> native best effort
with actionable warning when required scope/privacy/native capability is
proven. Actual OOM/disk failure -> ERROR not FAIL, no implicit retry.

### Percentage override acceptance and lifecycle (approved extension)

Use checked integer arithmetic without intermediate overflow (or arbitrary
precision followed by native range checks), conservatively floor to supported
native units. Apply existing zero, verified no-spill, shared memory-backed
scratch, required-control and cleanup rules identically across modes. No
arbitrary minimum or silent fallback. Observe capacity freshly before each
admitted check in both CLI and embedded paths. Growth or shrinkage changes
automatic and percentage targets next check; fixed requests stay fixed except
known-capacity adjustment. No live resize, autoscaler invocation, reservation
or promise that capacity remains available; invisible capacity is not assumed.

| Acceptance variant | Mandatory implementation proof (A1/A3/A4/A6/A10/A12/A13; R2-R4/R6/R7/R10; P1-P6) |
| --- | --- |
| Configuration | Omitted/empty outer mapping; independent auto/fixed/percent modes; 1/50/75/90/100; reject 0/101/negative/bool/float/string/null, conflicting mode members, empty mode maps, duplicates and unknown keys; project/target/connection precedence, atomic replacement and resets, wrong adapter, unselected/unreferenced policy, same-context alias equality/conflict, compile/parse and injected-loader compatibility. |
| Pure policy | Exact byte arithmetic, non-divisible capacity, native unit flooring, overflow/native domain, zero vs unknown, partial facts, native recommendation below explicit percent, independent dimensions, fixed known-capacity adjustment. |
| Changing capacity | Same project and percentage across RAM/disk increase and decrease; recompute per check; fixed unchanged until capacity cap; automatic native recommendation clamp; CPU unchanged; no mid-check resize. |
| Failure/advice | Unknown explicit percent denominator refuses before affected data reads; automatic and fixed behavior unchanged; bounded sanitized actionable diagnostic, partial scope warning; no silent fallback or mismatch; actual native error is ERROR. |
| Native integration | Both modes of invocation, all nine check families, four pinned engines and representative older/current OS/Python; actual setting effects, bounded exact results, real spill/insufficient disk, memory-backed scratch, cancellation, cleanup and unrelated observer unchanged. Distinguish injected arithmetic proof from measured native effects; controlled changing capacity. |

BDD: Given unchanged configuration `managed-memory: {percent: 75}` and observed
headroom 16 GiB, 32 GiB, then 8 GiB across checks, request 12, 24 and 6 GiB
respectively, subject to native representation and required protection;
unrelated sessions unchanged. Given unknown headroom, refuse the explicitly
percentage-configured affected check and advise alternatives. Automatic
missing optional evidence remains best effort where safe. Fixed 12 GiB
stays fixed at 16/32 GiB headroom and adjusts down at 8 GiB.

Responsibility: existing config/profile loaders validate and separate authored
policy from connection payloads; one resolver owns scope/precedence and alias
conflict admission; pure adapter-local calculation consumes fresh typed
observations; adapter owns native application/effect proof; existing service
and CLI own safe advisories. No duplicated resolver, global DuckDB defaults,
new mandatory adapter method or separate executor.
Extend existing `local-adaptive-resource-targets` capture; record actual test
nodes at implementation exit, not fabricated passing nodes. Future adapters
with elastic capacity independently assess automatic, relative and absolute
controls where native semantics support them; no universal percent or syntax.

### Cross-adapter design audit and required dispositions

| Risk | Resolution / owner |
| --- | --- |
| Global local-only resource knobs or engine-native defaults leaking into other adapters | M8.1.2 adapter namespace and per-context selection; native semantics only. Future adapter prework Gate 4L. |
| Deployment/connection precedence, inherited fixed vs relative mode, accidental weak admin limit | M8.1.2 typed layers, atomic replacement, explicit reset; defaults not security quotas. M28 typed env/CLI overrides and any hard admin policy before expansion. |
| Policy mistaken for connection identity or credentials | M8.1.2 keep separate; preserve ADR 0020 identity, factory payload, selected profile, secrets, plain parse/compile, and same-binding behavior. Gate 4J/4I regression proof. |
| Shared execution, aliases, concurrent load and multiple engines | M8.1.2 refuse only ambiguous same-context conflicting authored policies, no blanket process refusal; M8.2 cumulative/run concurrency and lifecycle; M13.5 cross-context budgets/transfer. |
| Freshness and cached/selected work | M8.1.2 capacity per check, no plan-dependent hidden fallback; M10.5 freshness, M10.6 selected scope, M10.7 onboarding, M10.8 restored binding scope. |
| Runtime policy changes mistaken for reconciliation semantics or leaked as evidence | M8.1.2 preserve contract/compiled plan meaning and privacy; M8.3 C10 safe effective-policy provenance, M9 evidence and M32 integrations. |
| Generic adapter API churn and future capability assumptions | Keep current API and private local collaborators; M11-M13 each adapter owns native resource schema, defaults and permissions; M29 shared contract and test kit, distributed adapters recheck actual driver/executor/cluster scope. |
| Premature hard quotas, dynamic autoscaler orchestration, profile-level settings in contracts | Non-goals now; M28 overrides and M40 hosted tenant quota/authorization separately gated. No automatic warehouse resize, remote tuning or data movement. |

No completed milestone reopening recommended: M2 project config and M6
profile/adapter foundations remain valid; M7.2-M7.4 and M8.1.1 retain their
existing binding/execution/semantic contracts. M8.1.2 owns additive changes
at those existing seams and regression verification; reopen a completed
milestone only if concrete proof exposes an incompatible prerequisite.
M9.5 mandatory type work and M10.8 scope restoration remain unchanged.
Before first external adapter at M11-M12, design and prove adapter-owned
schema discovery/registration and version compatibility without requiring
Core changes for each subsequent adapter. Do not invent a public extension
API now; preserve the single resolver and make missing/unknown support
explicit. No new milestone, no ecosystem repository before existing checkpoints.
Check both positive and negative config/profile integration for no-op
unreferenced policy, same-context conflicts, native observer isolation,
redacted paths/numbers/credentials, deterministic resolution, and no
accidental profile loading in plain parse/compile. Record actual test nodes
and capture dispositions before exit. No runtime or gate completion claim.

### Private temporary storage and failure behavior

Unique fresh per-check directory under existing selected trusted base
(default standard temp base). No persistent project namespace, recovery
ticket, lease, process ownership or old-directory sweep. Linux standard
exclusive mode 0700 directory; use actual owner/mode and trusted base
relationship, avoid unsafe parent rename/redirect boundary. macOS also
strip inherited ACL grants on newly created empty owned directory before
data (native chmod -N/maintained equivalent, fixed argv/no shell, verify
actual absence of grants); keep targeted verification, not recursive
ancestor ACL enumeration as default. Windows standard mode 0700 where
actual protected directory privacy supported; otherwise use minimal
native protected DACL create (reuse proven CreateDirectoryW primitive,
not entire old namespace/security system), actual directory and file
inheritance privacy before spill. Choose by supported capability and
proof, not OS version allowlist; no data written before private access
established. No unverified or shared-parent adoption. Use only documented
trusted cooperative parent scope; not a hostile privileged/same-user
sandbox. Refuse affected setup when actual privacy/ownership cannot be
proven; optional FS identity/classification missing is not refusal.
Prevent deletion of unrelated/replaced/live storage, use standard safe
cleanup of current verified owned directory after close. No automatic
abandoned recovery, crash residue can remain; document operator/OS
retention cleanup only for known inactive owned folders. No unknown path
sweeping. Current native/scratch cleanup failure safe error + L1 affected
context, unrelated old residue no block.

Evidence: 45920872979 POSIX four lanes passed; actual macOS inherited
allow despite 0700 removed from empty directory, leaf no grants, collision
refusal, clean and unrelated retained. 45920973672 all four Windows
lanes passed after canonical test parent correction: protected owner-only
native create and file inheritance (zero untrusted effective allow),
collision retained, cleanup. Standard 3.11 shared parent exposes inherited
allow, 3.13 tested standard creation private. No actual different-user
access, hostile replacement/ancestor or all-filesystem guarantee yet.
At implementation prove actual private spill on representative platforms,
including default ACL inheritance Linux, safe parent/replacement,
failure injection, incomplete API, normal/error/cancel and abrupt exit
no adoption; keep targeted platform mechanisms only when needed.
A future platform can work via equivalent actual capability, not label.

### Diagnostics, responsibilities and required proof before exit

Use existing service diagnostics and CLI terminal output on both success
and failure. Safe bounded deduplicated advisory describes missing
dimension or reduction, consequence, continue/refuse decision and actually
supported action (e.g. explicit managed setting, private disk-backed
scratch, independent normal invocation for native configuration conflict).
No raw database path, user value, SQL, native exception, result, environment
or secret. Warnings alone not reconciliation WARN/mismatch or exit change;
native actual errors ERROR, mandatory proof refusal not executed, preserve
primary plus cleanup diagnostic and L1. No result/state/artifact/sink or
public adapter schema changes; M8.3 structured projection remains.

Reuse existing config parser, pure scan-budget policy, verified native
control helpers and bound count reader (fetchmany(2), one expected row/
column shape, no LIMIT rewrite), current session, renderer and runner;
separate small adapter-local guard/actor and scratch collaborators if
needed. RunService preserves dependency injection; no alternate executor,
CLI mode detection, custom worker/transport, duplicated SQL/compare.
Reduce observation helpers to scoped best-effort facts and remove obsolete
worker, codec/proxy, watchdog and persistent namespace/ticket/recovery
candidate code only after approval; retain necessary native bounded/domain
and privacy test outcomes. Earlier A1-A13/R1-R10/B8-B10/P1-P6 and capture
ID disposition table below remains controlling for outcome coverage,
updated by this common path and exact proposed settings. No deferral of
embedded adaptive execution. M8.2 B8-B10 remaining invocation lifecycle,
M8.3 C10, M9.5 type, M10.8 scope, M11-M13/M29 and future adapter
assignments unchanged, no universal DuckDB mechanism imposed.

Implementation sequence after explicit approval: (1) inventory parked
candidate changes and approved retirement/replacement capture rows,
test-first scoped six-setting config/pure policy (precedence, reset, mode exclusivity, percent
arithmetic, changing capacity, unknown/zero/ranges/
precedence/no default cap); (2) minimal portable observations and native
controls/private scratch (actual effect and failure tests); (3) guarded
native bound session, bounded count, exact identity and noninterference,
actor/guard cleanup and L1, all nine families both modes; (4) canonical
admission and terminal advisories, remove interim guard only after
replacement tests pass, keep low-level helper compatibility; (5) full
standard CI plus persistent pinned/rolling native matrix, actual older/
current OS/Python/pin builds, synthetic future/missing API cases, real
larger-than-RAM spill, small costly workload, insufficient disk and
active-spill native interrupt, explicit override and measured final
tuning; (6) capture/index and branch-wide advisory, actual exact test
nodes and gate dispositions, docs/user guide/changelog; (7) mandatory
cumulative review-fix-revalidate loop on the entire branch until a fresh
review of the latest validated revision finds no actionable in-scope
findings and all exit proof is complete, then separate merge approval.
Apply the same loop and semantic anti-pattern checks within every
implementation/change iteration; report concise evidence-based status and
blockers as required by milestone-process.md. Critical safety assertion RED then
GREEN via CI when local unavailable. No fabricated node or green-job-only
proof. Existing Windows live-WAL-copy failure must be replaced with
equivalent actual portable fixture and verified, not waived. Prove
failure paths for actor initialization, native controls/attach/catalog/
guard/close/cleanup before any result becomes PASS. Persistent CI must
retain P1-P6, actual image/release/build/arch and version, periodic/
on-demand/release/change validation, coverage gaps and triage.

Approval requested for one common guarded native path, scoped six logical
settings with approved percentage modes, proposed project/target/connection
precedence and adjustable 50%/90% defaults, minimal observations,
no mandatory pressure monitor or automatic crash recovery, baseline
native conflicting-configuration refusal retained with advice.
Remaining actual implementation and exit proofs above are mandatory.
Do not treat this proposal as gate closure or implementation authorization.

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

### Embedded feasibility checkpoint (2026-11-27)

The guarded native alternative is distinct from the earlier unguarded ATTACH
candidate: keep one original ordinary read-only native connection for writer
exclusion and open a separate native memory instance with isolated settings
and native read-only attachment to the same approved file. Use the engine's
catalog name; a native catalog switch resolves the initial memory catalog
collision. Close the execution instance before the original read-only handle.
No process enumeration, custom worker or new public transport. Candidate
test-only integration into the existing bound session passed 77 selected
existing tests plus eight targeted filename, interrupt and concurrent-run
tests in each of eight environment combinations (45920605605). Actual
narrow and wide three-million-group reconciliations using disk spill with
same-file observer and read-only mounted fixture succeeded on all four pins
(45920361925 oldest, 45920605605 remaining). Observer unchanged, release,
cleanup and original file unchanged. This is feasibility, not production
proof. The previous unguarded spill failure had a test factory type error;
do not attribute it to the native engine.

Native ordinary reader refusal with incompatible same-file existing
configuration is reproduced on three newer pins (45920495382), including
the original connection form. No mutation of an unrelated instance.
Ordinary compatible readers and simultaneous independent attachments
succeeded. Existing Windows live-WAL-copy fixture fails on the unchanged
baseline too; preserve and explicitly resolve the coverage gap. Do not
promise arbitrary embedded configurations or remove existing capability
without approval. Evaluate a single guarded native path for both invocation
types to avoid mode detection and divergent implementations; compare the
extra native connection and catalog switch against ordinary CLI direct path.
No architecture selection or compatibility exception approved yet.

Remaining targeted probes: actual headroom-dependent native tuning versus
baseline and explicit overrides (45920824959), minimal private scratch
creation with observed inherited ACLs and no adoption of existing paths
(45920872979). No new numerical default, OS ownership subsystem or
dependency approved. Both paths must meet the same outcome gates.

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

Current implementation mapping replaces the historical proposed test names
and retired mechanisms. The approved A/R/B/P outcomes remain mandatory.
The following real test nodes and existing captured suites are the
verification index, not a standalone gate closure. Final exact-head
standard/native CI and cumulative review remain mandatory.

| Outcome | Actual implementation evidence and carryover |
| --- | --- |
| A1/R4 | `tests/config/test_project_config.py::test_scoped_resource_policy_accepts_documented_modes`, `::test_scoped_resource_policy_rejects_invalid_modes_without_leak`, `::test_scoped_resource_policy_rejects_wrong_envelope`, `::test_scoped_resource_policy_rejects_duplicate_mode_key`, `::test_local_resource_policy_mib_overflow`; `tests/profiles/test_loader.py::test_selected_target_resolves_scoped_resource_policy_precedence`, `::test_selected_target_keeps_operational_policy_out_of_connection_payload`, `::test_selected_target_rejects_duckdb_policy_for_non_duckdb_connection`. |
| A2/R4 | `tests/services/test_run_service_aggregate_admission.py::test_explicit_footprint_policy`, `::test_large_native_database_without_default_cap`; actual large narrow/small wide calibration above. |
| A3/R1/R5 | `tests/adapters/test_duckdb_bound_execution.py::test_optional_catalog_estimate_validates_native_shape`, `::test_optional_estimates_follow_check_roles`, `::test_optional_catalog_estimate_unknown_and_overflow`, `::test_malformed_catalog_evidence_is_not_scope_refusal`; `tests/services/test_run_service_aggregate_admission.py::test_optional_native_input_row_estimate_is_role_summed`, `::test_unavailable_catalog_estimate_is_advisory_only`. |
| A4/R5 | `tests/adapters/test_duckdb_bound_execution.py::test_file_scope_admission`, `::test_lease_invalidation`, `::test_file_drift_invalidates_active_lease`, `::test_quoted_relation_and_temp_shadow_keep_exact_binding`, `::test_actual_attached_catalog_is_not_local_base_table`, `::test_guarded_native_actor_excludes_writer_without_observer`; `tests/services/test_run_service_bound_execution.py::test_preflight_never_opens_session`, `::test_actual_session_and_aliases_writer_conflict`, `::test_project_run_alias_policy_uses_resolved_scratch_and_precedence`; `tests/services/test_run_service_duckdb_execution.py::test_run_service_blocks_key_safety_duckdb_wal_sidecar_before_adapter_setup`. |
| A5/R1/R8 | `tests/adapters/test_duckdb_bound_execution.py::test_bound_count_reader_rejects_invalid_rows`, `::test_bound_count_reader_rejects_extra_columns_before_fetch`, `::test_bound_count_reader_preserves_exact_count_and_diff`; existing `tests/adapters/test_duckdb_aggregate_transport.py` and `tests/adapters/test_duckdb_aggregate_numeric_domains.py` suites; `tests/services/test_run_service_aggregate_admission.py::test_native_aggregate_service_numeric_outcomes_and_privacy`. |
| A6/R9 | `tests/services/test_run_service_bound_execution.py::test_project_resource_advisories_are_safe_and_do_not_change_outcome`; `tests/services/test_run_service_aggregate_admission.py::test_optional_native_input_row_estimate_is_role_summed`, `::test_unavailable_catalog_estimate_is_advisory_only`, `::test_fresh_native_targets_for_each_check_and_both_invocation_paths`. |
| A7/R5 | `tests/services/test_run_service_aggregate_admission.py::test_all_nine_checks_use_owned_transaction_and_qualified_queries`, `::test_native_aggregate_service_numeric_outcomes_and_privacy`; existing aggregate, key-safety, row-count, numeric domain and low-level adapter suites. Expanded BIGNUM coverage remains M9.5. |
| A8/R8 | `tests/config/test_project_config.py::test_scoped_resource_policy_rejects_invalid_modes_without_leak`; `tests/adapters/test_duckdb_native_resource_controls.py::test_native_setup_error_is_sanitized`; `tests/services/test_run_service_bound_execution.py::test_project_resource_advisories_are_safe_and_do_not_change_outcome`, `::test_primary_outcome_retained_on_cleanup_failure`; `tests/services/test_run_service_aggregate_admission.py::test_native_aggregate_service_numeric_outcomes_and_privacy`. |
| A9/R1/R8 | `tests/profiles/test_loader.py::test_selected_target_keeps_operational_policy_out_of_connection_payload`; `tests/services/test_run_service_aggregate_admission.py::test_all_nine_checks_use_owned_transaction_and_qualified_queries`, `::test_large_native_database_without_default_cap`; `tests/services/test_run_service_duckdb_execution.py::test_run_service_does_not_mutate_stale_outputs_during_actual_key_safety`, `::test_run_service_does_not_mutate_stale_outputs_during_executable_row_count`; existing public-contract/import tests. M8.3 owns structured projection. |
| A10/R2/R3 | `tests/adapters/test_local_resource_observation.py::test_visible_v2_scope_reads_only_matched_membership`, `::test_visible_v2_memory_probe_failure_preserves_cpu`, `::test_scratch_filesystem_evidence`; `tests/adapters/test_portable_resource_observation.py::test_missing_provider_is_partial`, `::test_memory_probe_failure_does_not_erase_affinity`; `tests/adapters/test_duckdb_native_resource_controls.py::test_native_control_application`; actual platform and constrained evidence. |
| A11/R1/R9 | `tests/services/test_run_service_aggregate_admission.py::test_large_native_database_without_default_cap`, `::test_optional_native_input_row_estimate_is_role_summed`; measured narrow/wide evidence above. No unjustified size/work inference. Richer work/transfer analysis remains M12.5; authored modes M24/M25. |
| A12/R4/R10 | `tests/check_engine/test_local_resource_targets.py::test_automatic_parallelism_uses_known_managed_memory_without_admission_floor`, `::test_memory_aware_threads_preserve_authored_memory_modes`, `::test_relative_targets_follow_changing_capacity`; `tests/services/test_run_service_aggregate_admission.py::test_fresh_native_targets_for_each_check_and_both_invocation_paths`; measured candidate and actual production evidence above. Recheck tuning/native/deployment changes. |
| A13/R3/R5/R6 | `tests/adapters/test_duckdb_native_resource_controls.py::test_native_spill_setting_effect_not_readback`, `::test_required_control_readback_mismatch`, `::test_explicit_spill_failure_does_not_fall_back_to_automatic`; `tests/adapters/test_duckdb_bound_execution.py::test_unverified_required_setting_prevents_transaction`, `::test_guarded_native_actor_preserves_catalog_and_reader`, `::test_actual_guarded_native_interrupt_during_spill`. |
| B8/R6 | `tests/adapters/test_duckdb_bound_execution.py::test_native_interrupt_request_is_not_release`, `::test_native_interrupt_after_close_is_not_accepted`, `::test_actual_guarded_native_interrupt_during_spill`; M8.2 owns full invocation interrupt/deadline/retry and external termination. No in-process crash containment. |
| B9/R6/R8 | `tests/adapters/test_resource_scratch.py::test_check_scratch_requires_confirmed_native_close`, `::test_check_scratch_replaced_directory_is_not_deleted`, `::test_check_scratch_retains_storage_when_privacy_changes`, `::test_check_scratch_abrupt_exit_leaves_residue_without_blocking_next_check`, `::test_check_scratch_protects_windows_directory_and_file`, `::test_check_scratch_removes_inherited_macos_grants`; `tests/services/test_run_service_bound_execution.py::test_cleanup_failure_is_check_local_or_stops_native_execution`, `::test_primary_outcome_retained_on_cleanup_failure`. M8.2 owns run-wide cleanup. |
| B10/R7 | `tests/services/test_run_service_aggregate_admission.py::test_all_nine_checks_use_owned_transaction_and_qualified_queries`, `::test_fresh_native_targets_for_each_check_and_both_invocation_paths`; `tests/services/test_run_service_bound_execution.py::test_cleanup_failure_is_check_local_or_stops_native_execution`, `::test_native_failure_isolation_across_database_files`. M8.2 owns cumulative/concurrent scheduling. |

BDD: default execution of a file larger than RAM can complete with native
spill where supported; the same contract on different environments uses
different effective settings, with unchanged exact comparison semantics.
Explicit footprint refusal precedes data reads; unavailable optional
estimate warns without blocking. Native failures are ERROR, never
mismatch; OS termination returns no result and cannot prove cleanup.
Unrelated observer stays unchanged. Fresh private storage is removed only
after confirmed native close; uncertain current residue is retained and
affected work latched. Later invocations never adopt or sweep old storage.
No hidden retry, filtering, sample, output or scope change.

Regression capture metadata retains applicable original rows and IDs,
including retired worker-named IDs mapped to native exact results,
binding and lifecycle tests. The index routes actual changed source and
test paths; the branch-wide advisory and actual pytest collection must
confirm the current mapping. Historical worker/IPC/pressure-monitor and
persistent recovery test proposals are superseded, not pending coding
authority. Future R1-R10/P1-P6 and M29 gates retain applicable outcomes,
not forced DuckDB mechanisms.


## Outcome and diagnostic contract

Use existing configuration error taxonomy for malformed YAML and settings
(`RC_CONFIG_INVALID_PROJECT_CONFIG`); suppress unknown authored field values
and untrusted native text in newly introduced diagnostics. Preserve existing
placement, prerequisite, artifact, capability and L1 precedence. The
following table records current native-first outcomes and diagnostic codes;
review the public inventory before release.

| Case | Expected outcome and safe code |
| --- | --- |
| Explicit physical footprint over ceiling | not_executable / scan_budget_exceeded / RC_RUNTIME_SCAN_BUDGET_EXCEEDED; no data read |
| Required binding unavailable | not_executable / bounded_local_scan_required / RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED; no data read |
| Unsafe executing preflight | not_executable / unsafe_scan_preflight / RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT |
| Required resource evidence/control unavailable before work | not_executable / existing bounded_local_scan_required reason, RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE; no data read |
| Explicit estimate threshold exceeded after admission | existing comparison status, RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY |
| Configured estimate threshold cannot be evaluated | existing comparison status, RC_RUNTIME_ESTIMATED_INPUT_ROWS_UNKNOWN |
| Best-effort observation limitation or reduced effective target | existing comparison status, RC_RUNTIME_RESOURCE_ADVISORY |
| Setup or native data execution failure | error / existing RC_ADAPTER_CONNECTION_FAILED or RC_ADAPTER_QUERY_FAILED; safe fixed message |
| Returned native resource exhaustion or interruption | error / RC_ADAPTER_QUERY_FAILED; no comparison values |
| OS termination (e.g. kernel OOM) | no returned result or guaranteed cleanup; invocation-level handling remains M8.2 |
| Invalid transport or binding drift | error / RC_RUNTIME_BINDING_PROOF_FAILED or RC_RUNTIME_AGGREGATE_RESULT_INVALID (numeric evidence), no raw payload |
| Native/scratch cleanup cannot be confirmed | error / existing RC_ADAPTER_CLOSE_FAILED, L1 RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE for subsequent affected checks; preserve primary diagnostic |
| Abandoned scratch from an earlier invocation | never adopt or sweep; fresh independently private storage; no automatic recovery or discovery guarantee |

Unknown optional metadata is neither zero nor a hard admission reason.
Missing required proof cannot be converted to a warning. Explicit footprint
limits cover row count as well as key and aggregate families; this is an
opt-in restriction, not a default change. Existing prepared adapter helpers
retain their current behavior. No stable public reason enum or signature
addition is needed for this design; if implementation finds existing
taxonomy cannot express required behavior, reopen compatibility/design review
rather than silently coerce it. Warning diagnostics must be emitted safely on
success and failure without changing status or exit category.

## Historical implementation sequence and test plan (superseded mechanisms)

The current authorization and native-first sequence above control work. This historical sequence is retained for outcome traceability, not worker or recovery implementation authority.

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

Design approved for documentation integration. Implementation is authorized and in progress; exit approval is pending. The measured automatic tuning, native observation/dependency choices,
exact bounded native results, current scratch ownership and lifecycle
proof must be verified on the final revision before exit. If a required mechanism cannot be safely implemented, stop for
design correction and approval; do not narrow capability or mark gates done.

## Mandatory platform compatibility acceptance (P1-P6)

Apply the [Gate 4L platform subfamilies P1-P6](execution-resource-safety-assignments.md#mandatory-platform-compatibility-and-graceful-degradation-gate-4l) in addition to every existing A/R/B obligation. This is an approved refinement of this phase, not a new runtime allowlist or a scope expansion.

| Family | Required variants and expected behavior | Actual test/evidence mapping (final exact revision revalidation required) |
| --- | --- | --- |
| P1 / A2,A7,A10 | Unknown/new/older OS or compatible engine/dependency version with independently verified required controls; exact comparison, no label-only refusal/warning. | `tests/services/test_run_service_bound_execution.py::test_future_platform_observation_label_does_not_refuse_verified_native_scope` (synthetic observation label, actual native execution); native all-nine trace and real platform matrix. |
| P2 / A3,A6,A10 | Missing/changed/denied/malformed optional facts; preserve independent evidence, distinguish unknown and zero, continue with advice when safe. | `tests/adapters/test_local_resource_observation.py`, `tests/adapters/test_portable_resource_observation.py`, `tests/services/test_run_service_bound_execution.py::test_project_resource_advisories_are_safe_and_do_not_change_outcome`, `tests/services/test_run_service_aggregate_admission.py::test_unavailable_catalog_estimate_is_advisory_only`. |
| P3 / A4,A13 | Missing required protection refuses affected execution; actual native error ERROR; preserve unrelated context and L1. | `tests/adapters/test_duckdb_native_resource_controls.py::test_required_control_readback_mismatch`, `test_explicit_spill_failure_does_not_fall_back_to_automatic` in same module; `tests/services/test_run_service_bound_execution.py::test_project_run_applies_selected_native_policy`, `test_cleanup_failure_is_check_local_or_stops_native_execution` in same module; actual low disk calibration 46020823693. |
| P4 / A6,A8,A9 | Bounded actionable warning on success/failure, no status/exit change or raw data; captured terminal advice. | `tests/services/test_run_service_bound_execution.py::test_project_resource_advisories_are_safe_and_do_not_change_outcome`, `tests/services/test_run_service_aggregate_admission.py::test_fresh_native_targets_for_each_check_and_both_invocation_paths`; M8.3 structured publication remains mandatory. |
| P5 / A10,A12 | Distinct older/current platform evidence, constrained/capable and native effects, synthetic future/API variants. | `tests/adapters/test_duckdb_bound_execution.py::test_actual_guarded_native_interrupt_during_spill`, `tests/adapters/test_duckdb_native_resource_controls.py::test_native_spill_setting_effect_not_readback`, actual private scratch tests, calibration 46020054117/46020823693, actual release/build/arch/job evidence in compatibility matrix. |
| P6 / A12 | Persistent pinned/rolling matrix, periodic/manual/change/release triggers, capture and triage. | `.github/workflows/native-resource-compatibility.yml`, compatibility matrix, existing regression-capture metadata/index, actual CI 46020772995; cumulative exact final validation and branch-wide advisory remain required. |

The current mapping supersedes earlier planned worker and IPC test nodes.
No version label is a runtime support decision; actual untested OS capabilities
are not certified by synthetic label tests. Native effects and applicable
privacy/scope/cleanup tests remain required. User-facing CLI/config/limitations documentation and
changelog must describe actual supported alternatives, warnings, best-effort
versus required protection, and tested versus untested versions. Do not
advertise these features as available on main before implementation merges.
