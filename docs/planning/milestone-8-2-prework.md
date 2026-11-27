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
