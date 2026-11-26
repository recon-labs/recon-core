# Execution Scope Restoration and Expansion Assignments

## Status and gate

Maintainer approved temporary local base-table-only project-run scope for
M8.1.1 on 2026-11-26, consistent binding for row count/key/SUM checks,
fresh owned read-only connection per check, no automatic writable fallback,
and retention of legacy 64 MiB footprint guard only for key/SUM until
M8.1.2. Implementation pending. This is a temporary scoped MVP compatibility
restriction, not a universal architecture restriction. Gate 4Q owns the
restoration ledger below, in addition to Gates 4/4I/4L/4P, 4A/4B/4C/4J,
5/5E, 6 and 8/8C as applicable. R1-R10 and T1-T10 remain mandatory.

Existing row-count execution can reach ordinary views and non-project
DuckDB files via writable connection without the scan guard; key and SUM
already have narrower local base-table admission. Fresh in-memory project
connections do not expose an existing caller's populated database; borrowed
contexts, attached databases and cross-system comparisons are future
extensions, not previously supported project-run capabilities. Distinguish
restoration from new support; do not claim compatibility before proof.

## Pending capability ledger

| ID | Capability / required delivery | Primary implementation owner |
| --- | --- | --- |
| S1 | Restore relation-backed row count on explicitly authorized regular local DuckDB files outside project root; apply same path/identity, permission, admission and resource checks to keys/SUM. Explicit approved roots or file grants, no universal path trust or silent copying. | M10.8 |
| S2 | Restore safe ordinary local views, including nested views and dependency graph within authorized local base tables. Prove transitive bound lineage, cycles, external functions/side effects, actual scope and workload; unsupported definitions fail closed. Extend to existing key/SUM operations where proven. | M10.8 |
| S3 | Support explicitly authorized attached local catalogs and multiple file dependencies in a controlled same DuckDB execution context; prove each binding, read-only settings, identity, resource/transfer and cleanup. No implicit ATTACH or unapproved file access. | M10.8 |
| S4 | Support explicit caller-owned or isolated populated in-memory DuckDB context and same-process read/write coexistence workflow without writable fallback or arbitrary caller interference; design ownership, transactions, permissions, lifecycle, configuration isolation and lock conflicts. Distinguish actual borrowed context from a new empty :memory: database. | M10.8 |
| S5 | Controlled external file-backed relations/views (e.g. Parquet, CSV) with explicit file/scope authorization, format/metadata/identity, dependency and non-executing evidence, resource and privacy controls. No unrestricted glob, remote access, extension loading or side effects. Remote/object storage-specific support only after separate capability proof and explicit policy. | M10.8 local; M13.5 remote/cross-system |
| S6 | Cross-connection and cross-system reconciliation, including separately configured databases and PostgreSQL/Snowflake; explicit placement, compatible types, native pushdown, bounded summaries/movement or approved materialization, snapshot/freshness semantics, permissions and cleanup. No implicit Python fallback. | M13.5 |
| S7 | Authored SQL/query endpoints with dependency/scope and side-effect validation, explicit typed plan, wrapping and capabilities; reuse S1-S6 mechanisms, not a bypass. | M18 |
| S8 | Shared executable conformance for all claimed contexts, unsupported combinations, supported engine versions, resource/placement and privacy proof; no production adapter promotion without scoped proof. | M29 |

## Implementation and exit obligations

M10.8 is a mandatory post-MVP implementation milestone, not a research-only
checkpoint. It must restore safe local S1/S2 cases and implement scoped S3-S5
support, with explicit acceptance scope and tests for each family. M13.5 is
a mandatory post-MVP cross-context implementation milestone for S5 remote/S6,
after experimental adapter baselines and before later row-level/CDC claims
that depend on it. M18 and M29 retain S7/S8 obligations. No owner may close
with an applicable family only documented, untested, or moved to an unnamed
backlog. If a particular subcase is infeasible or needs later dependency,
obtain maintainer approval for a named implementation-bearing owner, update
ledger and gates, and publish limitation; no silent deferral. Do not promise
arbitrary views, arbitrary remote sources or all forms of borrowed sessions.

M8.1.1 and M10 exit must document the exact temporary restrictions, reason,
user workaround where safe (e.g. close a writer, use an authorized local
materialized base table under user's explicit control), and pending S1-S8
owners. M10 MVP release may proceed with these explicitly approved
temporary limitations, but M9.5 remains a hard release dependency.
M10.8/M13.5/M18/M29 exit requires actual native, bounded positive and
negative conformance for assigned scope. Mature capability claims and
production promotion cannot bypass these pending gates. Every affected
milestone audit expands applicable S/R/T families to exact acceptance
variants, BDD, responsibility map, diagnostics, ADR, tests, regression
capture and exit proof; review all pending rows even when earlier
milestones are completed. No hidden scope changes, copy/stage/cast or
query execution as preflight.

## Native evidence and current limitations

Temporary CI 45798041091 (four pinned DuckDB versions) completed 44 case
records. Same-file same-process RO/RW mixing rejected both orders; same
mode succeeds. Read-only permits temporary tables and settings mutation,
so connection ownership matters. Per-check transaction snapshot preserved
tested other-connection data updates and same-type table replacement in
writable test sessions, not concurrent RO/RW. Rollback/reopen succeeded
in tested scenarios; no general reuse guarantee. Native ASCII case
insensitive identifiers and distinct non-ASCII identifiers require
engine-correct resolution, not generic Unicode lower/casefold.
Tests are feasibility only; actual Recon bound execution, path/alias
proof, legacy view/outside-project regression, and full lifecycle
integration remain pending. Temporary experiment files removed.

## Next work

Approved M8.1.1 -> targeted M7.4 correction -> M8.1.2 -> M8.2 -> M8.3 ->
M9 -> M9.5 -> M10. M8.1.1 detailed prework/implementation approval is
still required. M10.8 and M13.5 are planning assignments only; exact
API/config, scope, safety, placement and compatibility decisions require
their own research and approvals. No production code authorized here.
