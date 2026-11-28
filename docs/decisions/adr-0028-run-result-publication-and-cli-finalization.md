# ADR 0028: Run-result publication and CLI finalization

Status: Maintainer-approved detailed design direction (2026-11-28).
Synthetic filesystem feasibility passed all nine maintained OS/Python lanes.
Final prework review and separate implementation approval remain required;
this record is not an implementation claim.

## Context

ADR 0027 and M8.2 establish a single invocation owner, validated loaded plan,
existing reconciliation status and primary exit mapping, cooperative stop,
confirmed native cleanup and private resource evidence. The current
execution-only result dictionaries contain data values and are not a durable
public contract. M8.3 introduces the first local result artifact and final
terminal projection, not another executor or evidence store.

## Decision

Publish a version 1 local JSON snapshot at run_results.json under the
configured target-path for normal CLI and RunService.execute invocations
after a trusted destination is available. One pure, explicitly allowlisted
projection consumes the existing sealed outcome and typed owner facts;
a dedicated artifact writer owns only safe path preflight, atomic staging
and cleanup. Service owns final command status, CLI renders it. Preserve
existing ServiceResult fields, exit categories, compiled-input workflow and
native semantics. No direct model dump or additional native work.

Validate the destination and invalidate the previous regular snapshot
before compiled/native work. No guessed cleanup when a trusted destination
is unavailable; reject unsafe path shapes without following redirects or
deleting unrelated data. After successful preflight, publish truthful early
failures, known-empty and stopped outcomes as well as normal comparisons.
Untrusted or unavailable records stay unavailable; complete scope does not
mean successful equivalence.

Write strict UTF-8 JSON to a uniquely and exclusively created same-directory
temporary file, flush and close, revalidate ownership and atomically replace
the reserved final file. No partial final document, copy fallback, hidden
retry, global lock or unknown-residue sweep. Failure to invalidate prevents
execution. Failed publication preserves primary outcomes and appends safe
diagnostics; exit 3 for prior 0/1/3, retain independent primary 2/4.
No false current artifact reference. Atomic visibility is not power-loss
durability or hostile-filesystem immunity.

Independent invocations may overlap. At a shared destination the actual
invalidation (unlink or observed absence) and atomic replacement operations
order the snapshots, not invocation start or first inspection. Later
preflight invalidation can legitimately remove an earlier publication.
Reject an observed identity change before unlink; portable stat/unlink is
not atomic compare-and-delete, and an overlapping replacement in the final
check/unlink window follows operation ordering. Failed post-preflight
cleanup never removes the final name or another invocation's staging data.
Written means this invocation committed, not continued file existence.
Correlate invocation identity with the command; use separate configured
targets for per-run retention. No run history, shared scheduler or lock.

Only canonical authored identifiers, approved status/diagnostic metadata,
structural counts and verified typed evidence are public. No source/target
row counts, values, keys, differences, raw policy payloads, relation or
connection names, private paths, SQL, profile data or raw errors. Resource
limits and readbacks are not actual consumption; unknown is not zero.
Preserve actionable safe diagnostics from proven owner-authored templates,
not trusted merely by diagnostic code; canonical identities come from
validated plan metadata, not engine text. Missing per-attempt accounting
must not become partial cumulative totals. Preserve explicit missing facts,
distinct cleanup and stop evidence, and existing status precedence. No estimate
re-execution or inference from diagnostic text. Publication follows the
execution seal and cannot retrospectively change a stop cause; the command
waits for publication and has no hard wall-clock guarantee.

## Alternatives

Direct serialization would expose private comparison data and bind public
schema to engine implementation. A second execution or reloading context
would undermine identity and scope. Writing directly to the final file
could expose incomplete evidence. Retaining a stale result without explicit
invalidation can mislead automation. History directories, global locks,
external stores and complex recovery add scope without being required for
this snapshot contract. Use explicit safe projection and portable local
atomic replacement rather than those alternatives.

## Consequences and proof

See [M8.3 prework](../planning/milestone-8-3-prework.md) for exact v1
fields, privacy, scope, failure precedence, resource metadata, tests and
ownership boundaries. Require actual cross-platform feasibility, production
writer and native-service proof, critical test-first regressions, full
cumulative A/B/C validation and separate maintainer approvals. Keep future
evidence, sink, selector, type and adapter gates. No new settings, API
version, dependency, release, schema migration or external repository.
