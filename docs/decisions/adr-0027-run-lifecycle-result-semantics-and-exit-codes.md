# ADR 0027: Run Lifecycle, Result Semantics And Exit Codes

Status: Design direction approved by maintainer (2026-11-27). Detailed interface and native feasibility proof tracked in prework; implementation and validated integration pending.

## Context

The current run service loads compiled artifacts and invokes the existing
engine. Invocation timing is incomplete, and the finish timestamp is
supplied before evaluation. Native check ownership, interruption and
confirmed cleanup already exist; invocation-wide lifecycle is separate.

## Decision direction

Use one invocation-local owner for identity, UTC labels, monotonic elapsed
time, explicit loaded plan, preparation, execution and finalization.
Preserve existing prerequisite resolution, status precedence and exit
mapping; distinguish invocation failure from reconciliation outcome,
primary failure from cleanup failure and stop request from confirmed
native stop/release. Unknown metadata stays unknown. Never publish a
completed success for incomplete/cancelled execution.

Keep explicit compile then run; validate loaded artifacts and actual
bindings but do not implicitly rebuild or claim authored-source freshness.
One native check at a time with existing adaptive native parallelism.
Optional positive invocation timeout, absent by default, applies to the
whole invocation; cooperative cancellation uses verified native stop
where available. No guaranteed hard process deadline. Cleanup can extend
past timeout. No automatic retry, process worker, global library signal
handler, physical resource guarantee or persistent scratch sweep.
Explicit caller retry starts a new invocation. No new resource YAML
policy or universal adapter setting.

Keep existing result model and command result surface; add only approved
typed, privacy-safe in-memory lifecycle metadata and necessary additive
reason/option semantics. No raw data, SQL, plan, paths, credentials or
native errors exposed. Existing status precedence and exit categories
remain authoritative; publication, final CLI projection, schema/version
and atomic output decisions belong to the separate run-result publication
phase. No selector execution, result/evidence writer or sink.

## Alternatives

Automatic compilation risks hidden rebuild and premature freshness
promises. Parallel scheduling, hard process isolation and automatic
retries add scope and can weaken snapshot and cleanup truth. Default
timeouts or arbitrary cumulative resource limits reject legitimate work.
The proposed scoped approach preserves explicit behavior while enabling
caller-controlled lifecycle management.

## Proof and consequences

See [execution lifecycle prework](../planning/milestone-8-2-prework.md)
for decision details, scope, acceptance dimensions, test plan, gates and
exit criteria. Native cancellation and race proof are mandatory before
claiming active stop support. If unsupported, revisit the decision rather
than silently degrading required behavior. No compatibility claim or implementation authority from design approval alone.

The detailed approved-direction refinement uses optional
`--timeout-seconds` and embedded keyword-only `timeout_seconds` and
caller-owned `cancel_event`. One monotonic deadline and first observed
stop cause; runtime stop maps to the existing runtime error category.
An invocation-local control owner coordinates the already existing native
interrupt with active-call return and confirmed cleanup, not query retry.
CLI-only main-thread signal coordination and a joined in-process execution
thread use the same runner; embedded calls install no signal handlers.
No OS-specific console modification or hard termination guarantee.
See the prework for exact non-execution reasons, timing, compatibility,
metadata ownership, cumulative envelope and required proof.
