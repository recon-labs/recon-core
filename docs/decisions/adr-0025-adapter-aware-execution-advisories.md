# ADR 0025: Adapter-Aware Execution Advisories

## Context

An identical logical reconciliation can have very different operational cost
and risk on different systems. A bounded result does not prove a bounded
database scan, and a warehouse's ability to process a large relation does not
prove that an operational database can safely supply or transfer it.

## Decision

Distinguish physical footprint, logical input estimates, operator/intermediate workload, configured controls and actual observed resources. Native controls and hardware-aware default calibration require supported-version evidence and bounded benchmarks. A small file, low estimate or bounded output does not prove safety; no arbitrary default, universal score or process-memory guarantee without proof. See [mandatory resource-safety assignments](../planning/execution-resource-safety-assignments.md).

Recon will distinguish execution admission from advisory guidance. Core owns
the final admission decision under explicit policy and typed plans. Adapters
may supply trustworthy, capability-specific non-executing evidence; neither
adapter nor user input can assert a successful budget decision directly.
Treat unavailable, malformed, unsupported and untrusted evidence explicitly.
Unknown required safety evidence or a hard limit violation blocks execution
as a non-execution outcome, not a reconciliation difference. Advisory
thresholds may warn on an otherwise admitted execution; a warning cannot
convert a hard block into an allowed execution.

The advisory model must distinguish scanned rows/bytes or partitions,
returned rows/bytes, transfer volume, and relevant engine-native workload
and cost evidence, including estimate units, provenance, availability and
uncertainty. Runtime/memory/timeout pressure, index use, partition pruning
and financial estimates are conditional on proven engine-specific evidence;
do not invent a price, duration, resource estimate or common cost unit.
Unknown optional advisory dimensions need not block otherwise proven safe
execution, but they cannot establish missing required safety proof.
Never execute a data-scanning plan to justify non-executing preflight.

Provide actionable, privacy-safe guidance when supported by evidence:
investigate indexing/pruning, prefer native pushdown and bounded summaries
where semantically equivalent, or propose explicit narrower comparison
scope, incremental windows, deterministic sampling or bounded failure detail.
A proposal is not accepted behavior. No hidden filters, sampling, casts,
fallback, unbounded transfer, automatic database mutation, or silent query
rewrite is allowed. Scope-changing advice must explain reduced coverage and
require explicit user choice; unavailable future capabilities must not be
presented as executable now. No raw plans, SQL, sensitive relation/key/value
data, or native error payloads in public advice by default.

The first bounded local policy owns the basic advisory foundation. Rich
metadata-driven recommendations and engine-specific proof belong to their
respective later work; stable production support requires shared conformance.
The build order and ecosystem roadmap own sequencing. Exact thresholds,
settings, evidence types, fields, wording, and backend estimate strategies
remain subject to milestone-specific research and high-risk prework.

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

## Alternatives and reasoning

A universal row-count threshold ignores workload and engine differences.
Warning-only policy can permit an unsafe run. Automatically rewriting queries
or selecting samples can invalidate equivalence. Separate admission,
conditional advisory evidence and explicit scope choices preserve both
resource safety and honest reconciliation meaning.

## Consequences

Conformance must cover known, unknown, unsupported, malformed, and unsafe
estimates; hard blocks versus nonblocking warnings; independent scan/result/
transfer limits; engine-native units; no implicit scope mutation; and sanitized
diagnostics, results and evidence. Use synthetic isolated fixtures, not
production experiments. ADR 0021 placement and ADR 0022 privacy and sink
boundaries remain authoritative. No current runtime, public schema, support
range or adapter capability is changed by this planning decision.
