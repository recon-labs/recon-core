# ADR 0024: Staged Ecosystem Incubation

## Context

ADR 0012 establishes Core-owned reconciliation semantics and a separate adapter
and resource package ecosystem. Waiting until every production extension
boundary is stable before testing an external SQL adapter can leave Core
overfitted to its local development engine. Creating many public packages too
early would instead introduce unstable interfaces, dependency and release
coupling, and misleading support claims.

## Decision

Complete the MVP and its release-readiness decision first. Then allow a
maintainer-approved experimental shared adapter test kit, followed by a first
external PostgreSQL adapter and a second Snowflake adapter, as independent
parallel work candidates. Keep DuckDB in Core until the official adapter
extraction gate. The ecosystem roadmap owns milestone timing; this ADR refines
the rollout portion of ADR 0012 without changing the official release boundary.

Experimental work must satisfy the existing pre-creation conformance design
and proof requirements, applicable privacy, artifact, profile, execution
placement and scan-safety gates, and scoped packaging and dependency decisions.
Use isolated synthetic data, pin Core/test-kit/adapter revisions, document
capability limits, and require semantic CI for every admitted operation. Do not
claim a stable API range or production compatibility from experimental proof.
Do not introduce broad scans, unapproved placement, sinks, or probabilistic
execution through experiments.

Core remains the source of truth for typed plans, validation, comparison,
diagnostics and evidence semantics. Adapters own system-specific connection,
metadata, native rendering and execution within admitted boundaries. A shared
test kit owns reusable conformance fixtures and assertions, not comparison
semantics. Experiments must not depend on private Core implementation modules
or invent parallel reconciliation rules. Missing extension points require
separate Core prework and approval. Keep existing Core regression coverage
until equivalent shared coverage is proven; carry forward unimplemented cases.

Official adapter releases, shared stable test-kit promises, DuckDB extraction,
packaging and release coordination remain subject to the complete adapter
conformance, packaging and extraction gates. Production compatibility is
capability-specific. No later gate is waived or marked satisfied by this ADR.

Resource packages can be incubated after their loaders and semantics exist;
official releases remain separately gated. Integration, documentation and
optional AI repos follow their own readiness gates and actual need.

## Alternatives and reasoning

Waiting for full official adapter readiness before any experiments minimizes
coordination but delays portability feedback. Extracting all adapters
immediately creates unstable extension contracts. Staged incubation allows
earlier bounded evidence without weakening the stable ecosystem boundary.

## Consequences and implementation guidance

Use the ecosystem roadmap checkpoints during each milestone audit and next-work
recommendation. Review readiness and carryover obligations, recommend parallel
work where appropriate, and record defer/block decisions. Each implementation
track has separate approved prework, a split decision, conformance matrix,
responsibility map, tests and exit review. Repository creation, publication and
promotion need explicit approval. No runtime, API, package version, supported
capability, or artifact contract changes are introduced by this decision.
