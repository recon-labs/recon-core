# Execution Resource Safety Assignments

## Mandatory gate and status

[ADR 0026](../decisions/adr-0026-local-execution-policy-and-scan-admission.md)
is reopened. Do not implement the earlier footprint-driven policy. Current
runtime is unchanged. ADR 0025 and existing binding, placement, privacy and
no-silent-scope-change rules remain requirements. Gate 4L owns resource
safety and admission; Gate 4I placement/transport, Gate 5 lifecycle, Gate 5E
output/cleanup, Gate 3L profiling and Gates 8/8C adapter conformance.

Every affected milestone must expand assigned families into exact acceptance
variants, diagnostics, test nodes, BDD, responsibility map, DoD and exit
proof. No readiness or exit with unassigned applicable requirements. Recheck
any added/moved execution, profiling, movement, write, cache or concurrent
work, even if not listed. Historical completed phases remain unchanged;
carry forward regressions when touched.

| ID | Requirement | Primary implementation ownership |
| --- | --- | --- |
| R1 | Independent physical footprint, estimated input, scan/work/intermediate cardinality, returned rows/bytes, transfer, actual observations and configured controls; provenance, units, availability, uncertainty. Unknown never zero. | M8.1 local; M11-M13 native; M12.5 richer analysis; M29 |
| R2 | Hardware/environment availability: RAM/CPU/cgroup/container constraints, disk/headroom, concurrent use; missing/misleading host information is not safety proof. | M8.1 |
| R3 | Native memory/thread/spill controls and bound read-only execution, enforcement capability, failure, configuration precedence, isolation/restoration; distinguish engine-managed memory from actual process ceiling. | M8.1; M11-M13; M29 |
| R4 | Useful measured defaults and explicit overrides; optional footprint cap considered separately, no arbitrary low threshold or unsupported hardware ratio. Larger safe workload versus small costly workload. | M8.1; M10; M29 |
| R5 | Non-executing actual binding and operation-aware admission, required scope fail closed, no executing plan preflight, hidden fallback, implicit filtering/sample or escalation. | M8.1; all execution expansions |
| R6 | Deadline/timeout, cancel requested vs confirmed stopped, interrupted/failed/not-executed outcome, cleanup and retry. M8.1 proves any control it relies on before admission. | M8.2; M8.1 prerequisite; M11-M13; M29 |
| R7 | Per-check and cumulative run resources, repeated scans, concurrency/fan-out; safe scheduling and budget scope. | M8.2; selectors/packs/profiling/state/integrations |
| R8 | Safe metadata handoff and durable projection, effective policy vs observed use, availability/provenance and resource outcomes, no raw plans/paths/data. | M8.1-M8.3; M9/31/32.1 |
| R9 | Evidence-based optimization advice: join growth, skew, width, repeated scans, pushdown/index/pruning, subset/window/sample, coverage tradeoffs; no automatic changes. | M8.1 basic; M12.5 deeper; M24/25 actual modes |
| R10 | Reproducible bounded synthetic scale/performance and failure probes across versions and resource envelopes; no universal guarantee or fixed SLA from probes. | M8.1 design/exit; M10; M10.5-10.7; M11-M13; M29 |

## Milestone checkpoints

| Milestone | Mandatory application |
| --- | --- |
| 9 | Budget evidence retrieval, export/movement, memory/disk and cleanup independently of output size. |
| 10 | MVP readiness requires useful zero-config and explicit-limit behavior on representative constrained/capable environments, larger-than-RAM cases where supported, and honest limitations. |
| 11 | Prove metric/group intermediate workload and native PostgreSQL operational safeguards at experimental checkpoint. |
| 12 | Distinguish metadata-only from scanning and bound catalog fan-out; prove native adapter metadata/resource capability. |
| 13 | Prove mapping/cast/width workload impacts and Snowflake warehouse-native resource, pruning and billing evidence at experimental checkpoint. |
| 15 | Reassess macro-generated operations and prohibit policy bypass. |
| 18 | Prove authored query read-only scope, non-executing evidence, binding and enforcement. |
| 19 | Recompute selected-scope and cumulative work; no hidden subset. |
| 21 | Prove join multiplicity, intermediate work, resource controls and bounded movement/detail. |
| 22 | Assess normalization and timestamp workload and pruning. |
| 23 | Budget hashing, canonicalization and confirmation workload. |
| 24 | Budget sample construction as well as comparison; sample size is not scan size. |
| 25 | Budget bootstrap, incremental windows, state reads/writes and samples; no silent full-scan fallback. |
| 26 | Bound CDC window scans, key movement, summaries and exact confirmation. |
| 27 | Bound asymmetric delete comparisons, state and transfer. |
| 28 | Resource CLI overrides require explicit precedence, validation and enforcement; debug cannot bypass. |
| 29 | Finalize shared version-specific native controls, evidence, resource envelopes, timeout/cancel/cleanup, bounded transfer/spill, useful defaults, unsupported cases and performance regression conformance before adapter promotion. |
| 30 | Budget JSON/nested expansion, width and extraction. |
| 31 | Bound export queries, rows/bytes, pagination, memory, disk, network and cleanup. |
| 32 | Integrations preserve budgets, retry/concurrency and cancellation semantics; no bypass. |
| 34 | Budget multi-grain fan-out and repeated comparisons. |
| 37 | Bound remote state I/O, retention, lock and retries. |
| 40 | Prove hosted tenant isolation, quotas, concurrency, cancellation and fair allocation separately. |
| 42 | Budget semantic expansion and generated comparisons. |
| 8.1.1 | Binding preflight and owned execution context; interim existing key/SUM footprint guard only. Binding portions of R3/R5/R6/R8/R10; no new resource defaults. |
| 8.1.2 | REOPENED - mandatory resource-policy implementation after verified M8.1.1 and targeted M7.4 correction. Own remaining R1-R10, A1-A13, measured defaults, optional footprint limit, non-executing workload evidence and proven native controls. Exact defaults and controls not locked. |
| 8.2 | Own deadlines, timeout/cancellation confirmation, connection/transaction/spill cleanup, cumulative run-resource budgeting and bounded concurrency policy; B8-B10. M8.1 must prove any control needed for its own admission before relying on it. |
| 8.3 | Publish allowlisted resource policy, actual versus estimated use, unavailable versus zero, enforcement and timeout/cancel/cleanup outcomes; C10. |
| 10.5 | Invalidate stale admission evidence, including policy, binding and environment changes. |
| 10.6 | Recompute admission and cumulative work for actual selected scope. |
| 10.7 | Teach resource settings, limitations and safe override behavior in onboarding. |
| 12.5 | Implement richer workload/plan analysis and evidence-backed recommendations, including cardinality/skew, join growth, repeated scans, widths, indexing/pruning, bounded profiling and explicit subset/window/sample coverage tradeoffs. |
| 15.5 | Budget expanded check packs and repeated work. |
| 24.5 | Budget combined sampling policy expansion and repeated work. |
| 25.5 | Bound sink writes, batches, retries, movement and cleanup. |
| 25.6 | Budget repeated profiling, history/drift scans and retention. |
| 25.7 | Budget rollup refresh/fan-out; no misleading completeness. |
| 27.5 | Bound propagation/fan-out and confirmation. |
| 32.1 | Publish only allowlisted resource evidence and bounded event transport. |
| 32.2 | Agent tools respect policy, cancellation and bounded outputs. |
| 32.5 | Budget action retries/fan-out separately; no unapproved mutation. |
| 42.5 | Budget AI-suggested execution/tool fan-out; suggestions do not authorize scans. |

## Reopened design prerequisites

Research official native settings and version limits, hardware/container
availability, memory outside engine buffer management, spill disk limits,
timeout/cancel feasibility, actual typed SQL and safe admission. Preserve
existing binding evidence. Benchmark authorized bounded synthetic small and
larger, compressed/uncompressed, skewed/grouped/repeated-scan/row-count
workloads across supported pins and available constrained/capable envelopes.
Measure footprint, estimated input, elapsed time, reliable process memory,
temporary disk, control effects and cleanup; document fixture truth, units,
limitations and unavailable evidence. Never use executing inspection as
production preflight. Use temporary CI fallback with explicit approval,
isolated fixtures and cleanup if local execution unavailable.

Compare optional footprint cap, hardware-aware defaults, explicit resource
envelopes and native enforcement; decide unknown/unsupported cases and
warning versus hard admission. No arbitrary replacement number. Determine
which timeout/cancellation controls are M8.1 prerequisites versus M8.2
lifecycle; reassess split. Record sources and experiments privately.
Present concrete proposed settings, defaults, compatibility and remaining
questions for approval, then revise ADR 0026, A1-A13 matrix, BDD, owner map,
test plan, DoD and implementation plan. Integrate approved prework before
implementation authorization. No new repository, implementation or
gate satisfaction is authorized here.

## Mandatory M9.5 delivery checkpoint

M9.5 mandatory type compatibility retrofit: assess R1/R3/R5/R7/R9/R10 for conversion and canonical key workload, intermediate growth, metadata binding, pruning, aggregate arithmetic, scheduling and supported-version scale; re-evaluate other R families when touched. M9.5 cannot bypass M8 admission or claim type proof as resource proof. See [type compatibility assignments](type-compatibility-assignments.md).

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is approved as direction, not implemented. Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

## Mandatory M8.1.2 resource policy handoff

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
