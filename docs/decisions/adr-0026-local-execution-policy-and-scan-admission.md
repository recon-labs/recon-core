# ADR 0026: Local Execution Policy And Scan Admission

Status: Reopened; implementation authorization suspended pending revised design.
Current runtime behavior is unchanged. The prior decision below is retained
as historical baseline. The inherited 64 MiB cap, hard footprint policy,
settings/defaults and resource enforcement are not locked for coding. See
[mandatory resource-safety assignments](../planning/execution-resource-safety-assignments.md). Preserve
binding, privacy and comparison semantics; revise policy with measured proof.
No replacement default or syntax is decided here.

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
