# Type Compatibility and Canonical Comparison Assignments

## Mandatory planning gate and status

Gate 4P (operation-aware type compatibility and canonical comparison) owns
the shared design. Gates 1A, 3/3A/3C/3D/3G, 4B/4C/4E/4F/4G/4H/4I/4K/4L/4O,
5, 6, 7 and 8/8C retain their applicable requirements. This is a delivery
assignment, not an approved type system, cast implementation, new authored
syntax or adapter capability. ADRs 0005, 0009, 0010, 0013, 0019, 0021 and 0026
remain authoritative; no silent coercion or relaxation of the existing
strict physical type checks. Historical M7.3/M7.4 exit remains recorded.
Do not claim production compatibility from the current MVP restriction.

Three independent decisions must be explicit: structural schema policy
(exact physical match vs declared logical compatibility), comparability
of an operation's input and result domains, and any user-authorized
normalization/conversion. A schema mismatch need not prevent a proven
lossless value comparison; a compatible schema does not prove correct
value comparison. Evidence must distinguish both outcomes. Native engine
implicit casts are not proof.

## Required families

| ID | Requirement |
| --- | --- |
| T1 | Define adapter-normalized logical types, physical type provenance and modifiers: signedness, ranges, exact/approximate numeric domains, precision/scale, length, collation/encoding, temporal units/timezone, binary, nested/extension types, nullability, unknown and unsupported metadata; no inference from observed values alone. |
| T2 | Operation-specific compatibility and directional conversion matrix: identical, losslessly comparable, explicit policy required, incompatible, unknown/unsupported. Prove symmetric equality or explicitly directed semantics, total representability or separately validated conversions. No universal physical-type equality requirement or generic string/float fallback. |
| T3 | Lossless integer width/signedness combinations, exact decimal scale/precision and integer-decimal domains; prove common representation, native SUM/result/subtraction domains, overflow and bounds, including grouped extrema and arbitrary precision where supported. No rounding/truncation or float promotion of exact values. |
| T4 | Approximate/mixed exact-approximate numeric decisions, finite values, signed zero, overflow/underflow, representation consistency separate from business tolerance, explicit semantics for numeric strings, failed conversions and loss. Keep existing supported native domains. |
| T5 | Strings/binary/boolean/UUID and temporal compatibility; collation, padding, case, Unicode, timestamp precision, offsets/timezones and DST; no implicit normalization, timezone or text-to-value guessing. Nested/JSON missing vs null, typed values and deterministic canonicalization. |
| T6 | Identity semantics: canonicalize keys before null/duplicate/uniqueness and missing/extra checks as applicable; detect conversion collisions and new nulls; prove composite keys, key prerequisites, grouped identities, join multiplicity and cross-domain equality. Never silently drop invalid/unmatched keys or count false matches. |
| T7 | Bind metadata, actual source/target relation identity, approved operations, conversion plan and execution to a consistent owned context; fail closed on stale/unknown proof. No hidden changes to connection/lifecycle/placement or scan scope; prove resource impacts of casts, scans, pruning, transfer, hash and intermediate growth under R1-R10. |
| T8 | Shared typed comparison plan and capability negotiation; Core owns semantics, adapter owns native mechanics; same-context, cross-connection and cross-system paths independently gated. Explicit mapping/policy precedence and versioned artifacts; no engine-specific implicit compatibility, unapproved fallback or public syntax promises. |
| T9 | Distinct diagnostics and outcomes for structural mismatch, non-comparability, conversion/overflow failure, unsupported/unknown evidence and executed data violations; preserve prerequisite blocking and privacy. Show safe effective policy, conversion direction and evidence provenance when approved; no raw values/keys/SQL by default. |
| T10 | Deterministic truth fixtures, positive/negative boundary cases, differential/native engine tests, round-trip or injectivity proof when appropriate, regression capture, supported-version/adapter/operation matrix, bounded scale proof, stable public contracts and carryover before claiming capability. |

## Delivery checkpoints

Each checkpoint expands applicable T1-T10 into concrete acceptance and
conformance variants, gates, ADRs, BDD, tests, owners, non-goals and exit
proof. No orphaned requirement or silent deferral. Exact type matrix,
default vs explicit policy, common-domain strategy, metadata model and
syntax must be approved through targeted research before implementation.

| Milestone | Required application |
| --- | --- |
| 7.3 / 7.4 corrective work | Preserve existing strict admission, numeric and null semantics; repair grouped SQL only after same-binding proof. Carry forward compatible-key/aggregate obligations to mandatory pending M9.5; do not use the correction to silently widen or reduce support. |
| 8.1 / 8.2 | Shared owned binding/snapshot prerequisites, qualification, resource/cast workload assessment, no stale metadata, lifecycle and cleanup. Assess whether prerequisite split must move before grouped correction. Do not lock resource calibration on defective renderer. |
| 8.3 / 9 | Distinguish structural, compatibility, execution and data outcomes; reserve safe policy/provenance visibility without prematurely changing artifacts. |
| 9.5 | Mandatory pending implementation owner: retrofit existing M7.3 keys and M7.4 scalar/grouped SUM with shared lossless exact type compatibility, including INTEGER/BIGINT and safely representable exact decimal domains. Complete T1-T10 applicable proof and preserve existing capability. After M8/M9 and grouped correction; before M10. See build order for scope and exit. |
| 10 | Hard release-readiness dependency: M9.5 must be completed and validated on main, not merely designed. Demonstrate actual support and document remaining unsupported combinations; no 0.1 tag/publish or M10 exit while M9.5 is pending. |
| 10.5-10.7 | Experimental shared test-kit inventory and artifact/cache/selector/onboarding semantics; no implied support. |
| 11 | Extend the completed M9.5 compatibility baseline to new metrics and grouped comparisons; independently prove approximate policies with Gate 4O. PostgreSQL experimental conformance. |
| 12 | Implement structural schema equality/compatibility and normalized metadata using the shared comparison model, not a separate divergent type system. |
| 12.5 | Metadata profiling/advice may suggest compatible types/conversions but never apply unapproved casts or infer total representability from samples. |
| 13 | Explicit source-target mappings, key mappings, policy resolution, Snowflake experimental native/cross-system evidence; no implied cross-system execution. |
| 15 / 18 | Macros and executable endpoints cannot bypass type proof, binding, capability or resource admission. |
| 20 / 21 | Defaults/precedence and row-level comparison; use shared typed domains, key collision checks, exact/numeric and string policy semantics. |
| 22 | Temporal precision, date/time/timezone, DST and explicit conversion/tolerance. |
| 23 / 24 / 24.5 | Canonical hashes, probabilistic summaries and reusable sample keys must preserve shared identity equivalence, not raw engine encoding assumptions. |
| 25 / 26 / 27 / 27.5 / 34 | Persisted identity, CDC, multi-grain keys and changes to type policy; no silent state reuse or collisions. |
| 29 | Mandatory shared adapter test-kit conformance, compatibility matrix and native dialect/scale proof before production promotion. |
| 30 | Nested/semi-structured logical types, JSON path/missing/null, canonicalization. |
| 31 / 32.1 / 35 / 36 | Safe evidence/lineage, stable public type-policy contracts, compatibility/migration and versioning. |

## Release and gate discipline

Current runtime remains strict. M9.5 is the mandatory implementation owner
for the historical M7.3/M7.4 compatibility gap. Before locking reopened
M8.1, confirm shared binding/correction sequence and M9.5 prerequisites.
M10 requires actual M9.5 implementation and exit proof, not a decision to
defer; M11 is expansion only. Any proposed sequencing or scope change
requires separate maintainer approval and synchronized assignment, build
order, gate, compatibility and private routing changes. No mature claim
until applicable native capability and conformance are proven.

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is approved as direction, not implemented. Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.
