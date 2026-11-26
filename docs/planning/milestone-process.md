# Milestone Process

## Purpose

This document defines the planning process for milestones, sub-milestones,
roadmap items, and epics. It applies to MVP, post-MVP, and future roadmap work.

Build-order documents can define sequence and capability homes, but this
document is the source of truth for milestone prework, high-risk conformance
matrices, and milestone split rules.

## Ecosystem recommendation checkpoints

For milestone audits, prework, phase exits and next-work recommendations, read
[the repository introduction checkpoints](ecosystem-roadmap.md#repository-introduction-checkpoints).
Review current and next milestone candidates and outstanding deferred candidates.
Report readiness, actual repo existence, prerequisites, gates, regression
carryover, and recommend now, already satisfied, defer with rationale, or
blocked. A recommendation is not permission to create, release, or modify a
repository. Parallel work has its own prework, split decision, acceptance
matrix when high-risk, and approval. Record dispositions so the next audit
can revisit them. Preserve official compatibility and extraction gates even
when early experiments are recommended.

## Lightweight prework

Before implementation starts for any milestone or equivalent roadmap work, a
lightweight prework artifact must be present, current, and consistent with the
roadmap, build-order docs, ADRs, compatibility docs, gates, and current
implementation.

The prework artifact must define:

- scope,
- explicit non-goals or out-of-scope items,
- expected behavior,
- affected docs,
- required tests,
- compatibility, security, and privacy impact,
- Definition of Done.

If this prework is missing, stale, or inconsistent, do the pre-milestone
alignment work before coding. Low-risk classification does not remove this
requirement.

## Mandatory execution resource safety checkpoint

For every milestone audit, prework and phase exit affecting execution, profiling,
movement, writes, caching, concurrent or generated work, evaluate the
[resource-safety assignments](execution-resource-safety-assignments.md), Gate 4L
and the applicable placement, lifecycle and conformance gates. Assign each
applicable R1-R10 family to the owning implementation phase and expand it into
concrete acceptance variants, test nodes, BDD, responsibility map and exit
proof. Record explicit rationale for genuinely non-applicable families. Check
new or moved execution paths and ecosystem introduction checkpoints. A reopened
ADR or unresolved required proof blocks implementation; prior approval does
not authorize coding a superseded design. No phase may exit by merely citing
this assignment or silently deferring an applicable requirement.

## High-risk upgrade

For high-risk milestones and public-surface changes, the lightweight prework is
not enough. Add a dimension-expanded acceptance/conformance matrix before
implementation.

The matrix must list:

- dimensions,
- cases,
- expected behavior,
- test coverage,
- docs or gate impact,
- out-of-scope rationale.

Every required row must map to a new test, an existing test, or an intentional
out-of-scope decision with rationale. Example-only coverage is not sufficient,
and examples do not prove coverage unless relevant dimensions and sibling
variants are enumerated.

## Implementation responsibility map

For high-risk milestones and public-surface changes, the implementation map must
include a responsibility map before coding starts. A source map says which files
may change; the responsibility map says what each module or component may own.

The responsibility map must list:

- module or component,
- allowed responsibilities,
- forbidden responsibilities,
- allowed dependencies or concrete coupling,
- expected helper boundaries,
- refactor triggers before phase exit,
- tests protecting the boundary.

The map should prevent behavior-heavy work from accumulating in one file simply
because the source map named that file. If implementation discovers a module
absorbing responsibilities outside its mapped boundary, pause before phase exit
and either complete a same-scope refactor or record why a broader refactor is
blocked and needs separate confirmation.

## Carryover Gates

Before milestone prework, implementation, or phase exit claims a high-risk or
public compatibility surface complete, check:

```text
docs/compatibility/regression-capture/index.yml
```

Match the work by `primary_milestone`, `applies_to`, and `trigger_surfaces`.
Applicable capture rows must be mapped to current tests, migrated into a future
shared suite, intentionally deferred, or marked not applicable with rationale.
Unresolved `pending` rows are blockers for the matching surface.

For example, profile-backed adapter diagnostic redaction should not only test
value-shaped diagnostic codes such as `RCsuper-secretLEAK` and `RC12LEAK`. The
matrix must also enumerate the sibling dimensions that can leak unsafe config
keys, including delimiter-separated key tokens such as `RC_PASSWORD_LEAK` and
separatorless key tokens such as `RCPASSWORDLEAK`, and must preserve safe adapter
codes that only incidentally contain non-secret config-key substrings, such as
`RC_ADAPTER_CAPABILITY_UNSUPPORTED`.

High-risk surfaces include public YAML behavior, CLI behavior, generated
artifacts, typed plans, adapter APIs, adapter capabilities, SQL rendering,
profiles and secrets, diagnostics and redaction, execution, runner/results,
evidence, failure details, sampling, state, watermarks, CDC, packages, external
integrations, adapter test kits, cross-repo compatibility, source-target mapping,
schema policies, tolerance/null/normalization execution, hashing, timestamps,
query endpoints, and macro-assisted behavior.

## Research Before Lock

Before locking a future gate or future milestone prework for implementation,
perform a milestone-specific research decision pass. Research is not a broad
background-reading requirement. Start from the concrete Recon decision area that
remains unresolved. If existing Recon docs, ADRs, gates, compatibility docs, and
implementation constraints already lock the decision, record
`research_decision: not-required` and continue.

When research is needed, select only the outside source categories relevant to
the unresolved decision, such as mature open-source tools and patterns,
available integration tools, relevant warehouse, orchestrator, catalog,
cloud-native, standard, specification, or protocol surfaces, and current
engineering pain points.

Convert the research into Recon-native decisions before coding:

- scope,
- non-goals,
- gate requirements,
- milestone mapping,
- acceptance/conformance matrix rows,
- tests,
- ADR and docs impact,
- compatibility impact,
- security and privacy impact,
- future integration notes.

Detailed source attribution, source links, comparison tables, named
borrow/adapt/avoid/defer/reject notes, vendor-specific rationale, and
source-specific research summaries belong in the private companion repository.
Public durable docs should state the final Recon decisions in Recon-native
terms.

Private research notes must record a Recon-fit judgment before any finding can
influence public prework, tests, gates, docs, ADRs, compatibility impact,
security/privacy impact, future integration notes, or implementation planning.
Use this decision shape in the companion repository:

```text
decision_area:
current_recon_authority:
unresolved_question:
research_needed: yes | no
source_and_access_date:
observed_pattern:
recon_fit_judgment:
outcome: borrow | adapt | avoid | defer | reject
why_this_fits_or_does_not_fit_recon:
resulting_action: scope | non-goal | matrix-row | test | gate | ADR/docs-update | compatibility-impact | security/privacy-impact | implementation-constraint | future-integration-note | no-action
public_docs_impact:
matrix_or_test_impact:
ADR_or_gate_impact:
compatibility_impact:
security_privacy_impact:
future_integration_note:
implementation_constraint:
```

The resulting public prework should contain only the final Recon-native decision
and its effect on scope, non-goals, gates, matrix rows, tests, compatibility,
security/privacy, docs, ADRs, future integration notes, or implementation
constraints.

## Milestone Step Plans

When milestone work is divided into executable steps, design the plan around the
decisions that must be locked, not only around files to edit.

Each step must be small enough to complete in one `do step N` request and must
include:

- objective,
- step type (`prework`, `research`, `docs-alignment`, `implementation`,
  `validation`, or `review`),
- decision questions to resolve,
- research applicability and `research_decision` status when the step may
  involve milestone prework research,
- expected public docs, private companion docs, code, or test changes,
- required reads with exact files and sections,
- validation,
- dependencies,
- stop conditions,
- commit or companion-update expectations.

Milestone prework step plans must follow this flow:

1. identify every Recon decision area that must be locked,
2. name the current Recon authority for each area,
3. decide whether targeted research is needed for unresolved areas,
4. convert research into Recon-fit judgments and final Recon-native decisions,
5. map those decisions into scope, non-goals, gates, matrix rows, tests, docs,
   ADR impact, compatibility impact, security/privacy impact,
   source/responsibility maps, future integration notes, and implementation
   constraints,
6. validate that no gate, matrix row, BDD/workflow scenario, test requirement,
   docs update, public contract concern, phase-exit requirement, or blocker is
   orphaned.

For any prework step that may involve research, record one of:

```text
research_decision: not-required
research_decision: completed
research_decision: blocked
```

If research is completed, the step must name the private companion artifact that
stores source-specific findings and explain how the findings feed the next
public prework, matrix, test, gate, ADR/docs, compatibility, security/privacy,
future integration note, or implementation-map step.

## Test planning

Tests must be derived from the milestone prework. For high-risk work, tests must
map back to the acceptance/conformance matrix. A milestone is not complete while
required behavior remains untested, undocumented, or inconsistent with the
accepted matrix.

For phased high-risk work, each phase exit should compare completed behavior,
tests, docs, newly discovered requirements, and remaining work against the
matrix before the next phase starts.

High-risk phase exits must also include a design-integrity review against the
responsibility map. The review should report material module growth, new
concrete adapter or infrastructure coupling, service or orchestrator boundary
leaks, duplicated helper logic, test-helper bloat, and whether a same-branch
low-risk refactor is required before the milestone can be considered complete.

## Review fixes and project consistency

Before a fix, identify currently supported behavior from the relevant docs,
ADRs, compatibility records, milestone prework, tests, regression capture,
and implementation. Documented, tested, intentionally implemented, or
in-scope behavior counts as supported even before a stable release.

Classify the fix as a local fix, a same-scope refactor, or a broader refactor
that requires approval. Prefer the smallest design-conformant change, not
the shortest patch that makes a local test pass. Classify capability impact
as preserving, expanding, shrinking, or unclear. A capability-expanding
change needs the applicable design and compatibility gates. If impact is
unclear, resolve the support boundary before editing.

Do not silently remove, reject, disable, or narrow supported behavior to
fix a bug. Present the options to preserve support now, preserve truthful
behavior with a future-gated follow-up, or explicitly approve a scope
reduction. Obtain explicit approval before narrowing support; align docs,
compatibility, changelog, tests, and regression capture if approved.

When a fix exposes a cross-cutting or future milestone requirement, add or
propose the relevant gate, conformance matrix row, test, ADR/docs,
compatibility note, or regression-capture row in the owning workstream.
Deferred work must have an explicit rationale and owner; do not hide
incomplete correctness behind a passing test or unsupported status.

After local validation, perform a second consistency pass across ownership,
dependencies, validation, diagnostics, privacy, public contracts, artifacts,
capabilities, tests, capture metadata, docs, and future gates. Correct
same-scope secondary drift before completion; stop for approval if the
required correction changes broader architecture, public behavior, or
scope. Record the decision and remaining follow-up.

## Mandatory cumulative review-fix loop

Authorized review-fix work and implementation-bearing phase or milestone
exit reviews must repeat the review-fix cycle until a fresh review of the
cumulative approved scope finds no actionable defects or material risks.
Review-only requests remain read-only; this process does not grant permission
to edit, commit, push, expand scope, or merge.

Each iteration reviews the full change against its base and relevant unchanged
collaborators, including docs, ADRs, contracts, acceptance dimensions, gates,
tests, regression capture, and responsibility boundaries. Record findings,
classify capability and design impact, and resolve authorized in-scope
defects. Non-trivial behavioral corrections require observed failing
regression proof (RED), the smallest design-conformant correction, and
verified passing validation (GREEN), including nearby supported behavior.
Non-behavioral corrections require appropriate objective validation.

After GREEN, perform the second consistency pass described above and repeat
the cumulative review on the updated revision. Passing tests, a patch-only
review, or a predetermined number of iterations is not sufficient to exit.
Do not weaken proof, narrow supported behavior without approval, or defer
in-scope correctness to reach completion.

Exit only after a fresh review on the latest validated revision finds no
actionable in-scope findings and the required exit evidence is complete.
If approval, a broader design change, missing gates, unavailable validation,
or another genuine blocker prevents continuation, report the unresolved
finding, blocker, and next action without claiming completion. Record the
reviewed revision, findings, validation, residual risk, and exit decision.
The absence of findings is not a guarantee that all possible bugs are absent.

## Milestone splits

Every milestone or equivalent roadmap work must include a split-or-justify
decision before implementation. High-risk milestones must either be dissolved
into decimal sub-milestones or explicitly justify why the combined scope is safe
as one implementation unit.

A missing gate, ADR, Definition of Done, acceptance/conformance matrix, BDD
scenario, or test plan does not remove this requirement. The split-or-justify
decision must still be recorded before coding, even when the missing artifact
already blocks implementation.

If a milestone is too broad, spans multiple high-risk surfaces, or cannot be
made safe as one implementation unit, dissolve it into decimal sub-milestones
such as `Milestone N.1`, `Milestone N.2`, and `Milestone N.3`.

The original milestone becomes an umbrella or superseded entry, not a direct
implementation target. Each sub-milestone must have its own scope, non-goals,
risk classification, prework, tests, docs/ADR/gate impact, Definition of Done,
and dependency or ordering notes. High-risk sub-milestones also need their own
dimension-expanded conformance matrix.

When a milestone is split, update roadmap, build-order, gate, ADR,
compatibility, and testing references so no orphan implementation plan remains.

Decimal sub-milestones must be implementation-bearing. Do not create a
sub-milestone whose build scope is only design, research, ADRs, matrices,
documentation, gates, or alignment work. Those items are prerequisite prework
assigned to the implementation sub-milestone they unblock. If only prework is
currently safe, record implementation as blocked and name the required prework.

## Split assignment matrix

When a high-risk milestone is split, the split is incomplete without a Split
Assignment Matrix. The matrix must include one row per implementation
sub-milestone and these columns:

- sub-milestone,
- concrete implementation scope,
- non-goals,
- high-risk surfaces touched,
- required gates,
- required ADRs or decisions,
- required docs updates,
- required acceptance/conformance matrix rows,
- required responsibility-map rows,
- required BDD or workflow scenarios,
- required tests,
- public contract impact,
- phase-exit review requirements,
- blockers before coding.

No gate, ADR, docs update, matrix row, responsibility-map row, BDD scenario,
public contract concern, test requirement, or phase-exit requirement may remain
assigned only to the umbrella milestone. If an item applies to multiple
sub-milestones, list it in each affected row. If ownership is unclear, block
implementation instead of guessing.

## Split workflow

Use a stepwise split workflow for high-risk milestones:

1. Audit milestone scope, high-risk surfaces, gates, docs, ADRs, tests, and
   current implementation.
2. Propose implementation-bearing sub-milestones.
3. Build the Split Assignment Matrix, including responsibility-map ownership.
4. Run the orphan check.
5. Update planning/docs after the split and assignments are internally
   consistent.
6. Validate references and report the future implementation plan.
7. Do not code until the assigned prework for the relevant sub-milestone is
   complete.

## Mandatory type-compatibility assignment review

For every milestone that introduces or changes metadata, schema checks, key or value comparison, normalization, aggregation, casting, hashing, mapping, persisted identities, adapter support or evidence, read [Gate 4P mandatory type compatibility assignments](type-compatibility-assignments.md). Expand applicable T1-T10 into gate proof, matrix, BDD, tests, owner/source map and exit checklist. Report unassigned obligations and stop before implementation if applicable design or proof is missing. Historical strict MVP behavior is not a permanent compatibility design. Review M9.5 prerequisites before locking reopened M8.1. M9.5 is a mandatory pending implementation milestone and hard M10 exit/release dependency; historical M7.3/M7.4 completion cannot satisfy it.

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is approved as direction, not implemented. Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

At entry and exit check all pending S rows, exact implementation ownership and proof, even if restriction originated in a closed milestone. No owner closure or reassignment without approved disposition.

## Equivalent validation when local execution is unavailable

Local execution is preferred, not a prerequisite when unavailable. Required
validation and milestone gates remain unchanged. Use equivalent repository
revision/diff inspection and CI proof without a separate local-execution
waiver. Pin base/head, inspect complete changed surfaces, review all
applicable gates, acceptance/test ownership, compatibility, privacy,
design integrity and orphaned requirements. Review branch-wide regression
capture decisions using the actual advisory command or an explicitly
documented equivalent inspection of its routing and capture requirements;
never claim an unexecuted command ran.

Prefer existing CI on the exact revision, including required pre-commit,
lint, formatting, typing, tests and supported native-version suites. Verify
actual jobs, commands, results and skips; preserve test-first RED/GREEN
and cumulative review requirements. When required proof is unavailable
from existing jobs, use narrowly scoped temporary CI validation on an
isolated branch with bounded synthetic fixtures, exact revision/version
and commands, minimum permissions, no secrets or production data, and
verified removal of temporary files. No temporary execution infrastructure
on main or product branches. Respect repository security and branch
protection. Record exact evidence, equivalent checks, missing proof and
cleanup. Missing required proof remains a blocker to readiness or gate
satisfaction, not a reason to weaken tests. Ordinary design, implementation,
merge and release approval requirements are unaffected.
