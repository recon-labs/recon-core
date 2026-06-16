# Milestone Process

## Purpose

This document defines the planning process for milestones, sub-milestones,
roadmap items, and epics. It applies to MVP, post-MVP, and future roadmap work.

Build-order documents can define sequence and capability homes, but this
document is the source of truth for milestone prework, high-risk conformance
matrices, and milestone split rules.

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
perform a milestone-specific research pass. The research should cover mature
open-source tools and patterns, available integration tools, relevant
warehouse, orchestrator, catalog, cloud-native, standard, specification, or
protocol surfaces, and current engineering pain points when those inputs are
relevant to the milestone.

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
borrow/avoid notes, vendor-specific rationale, and source-specific research
summaries belong in the private companion repository. Public durable docs should
state the final Recon decisions in Recon-native terms.

## Test planning

Tests must be derived from the milestone prework. For high-risk work, tests must
map back to the acceptance/conformance matrix. A milestone is not complete while
required behavior remains untested, undocumented, or inconsistent with the
accepted matrix.

For phased high-risk work, each phase exit should compare completed behavior,
tests, docs, newly discovered requirements, and remaining work against the
matrix before the next phase starts.

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
- required BDD or workflow scenarios,
- required tests,
- public contract impact,
- phase-exit review requirements,
- blockers before coding.

No gate, ADR, docs update, matrix row, BDD scenario, public contract concern,
test requirement, or phase-exit requirement may remain assigned only to the
umbrella milestone. If an item applies to multiple sub-milestones, list it in
each affected row. If ownership is unclear, block implementation instead of
guessing.

## Split workflow

Use a stepwise split workflow for high-risk milestones:

1. Audit milestone scope, high-risk surfaces, gates, docs, ADRs, tests, and
   current implementation.
2. Propose implementation-bearing sub-milestones.
3. Build the Split Assignment Matrix.
4. Run the orphan check.
5. Update planning/docs after the split and assignments are internally
   consistent.
6. Validate references and report the future implementation plan.
7. Do not code until the assigned prework for the relevant sub-milestone is
   complete.
