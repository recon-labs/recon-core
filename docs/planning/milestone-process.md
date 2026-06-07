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

For example, profile-backed adapter diagnostic redaction should not only test
value-shaped diagnostic codes such as `RCsuper-secretLEAK` and `RC12LEAK`. The
matrix must also enumerate the sibling dimensions that can leak unsafe config
keys, including delimiter-separated key tokens such as `RC_PASSWORD_LEAK` and
separatorless key tokens such as `RCPASSWORDLEAK`.

High-risk surfaces include public YAML behavior, CLI behavior, generated
artifacts, typed plans, adapter APIs, adapter capabilities, SQL rendering,
profiles and secrets, diagnostics and redaction, execution, runner/results,
evidence, failure details, sampling, state, watermarks, CDC, packages, external
integrations, adapter test kits, cross-repo compatibility, source-target mapping,
schema policies, tolerance/null/normalization execution, hashing, timestamps,
query endpoints, and macro-assisted behavior.

## Test planning

Tests must be derived from the milestone prework. For high-risk work, tests must
map back to the acceptance/conformance matrix. A milestone is not complete while
required behavior remains untested, undocumented, or inconsistent with the
accepted matrix.

For phased high-risk work, each phase exit should compare completed behavior,
tests, docs, newly discovered requirements, and remaining work against the
matrix before the next phase starts.

## Milestone splits

If a milestone is too broad, spans multiple high-risk surfaces, or cannot be
made safe as one implementation unit, dissolve it into decimal sub-milestones
such as `Milestone 7.1`, `Milestone 7.2`, and `Milestone 7.3`.

The original milestone becomes an umbrella or superseded entry, not a direct
implementation target. Each sub-milestone must have its own scope, non-goals,
risk classification, prework, tests, docs/ADR/gate impact, Definition of Done,
and dependency or ordering notes. High-risk sub-milestones also need their own
dimension-expanded conformance matrix.

When a milestone is split, update roadmap, build-order, gate, ADR,
compatibility, and testing references so no orphan implementation plan remains.
