# Repository Strategy

## Purpose

This document defines Recon Labs' intended multi-repo strategy.

`recon-core` is the first repo and source of truth, but Recon is designed to become an ecosystem.

## Current decision

Start with `recon-core`.

This repo contains CLI, framework concepts, core docs, contract model, check engine, result model, evidence generation, base adapter interface, early examples, and foundational ADRs.

## Long-term repo categories

### Core runtime

```text
recon-core
```

### Adapter packages

```text
recon-duckdb
recon-postgres
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

### Adapter test kit

```text
recon-adapter-testkit
```

### Check and policy packages

```text
recon-checks-cdc
recon-checks-migration
recon-checks-medallion
recon-policies-sampling
recon-policies-tolerances
recon-evidence-templates
```

### Examples and docs

```text
recon-examples
recon-docs
```

These may split later if they grow large.

### Hub

```text
recon-hub-index
```

## Why not one repo forever

One repo forever creates unnecessary dependencies, adapter release coupling, CI complexity, core bloat, and harder community ownership.

## Why not many repos immediately

Many repos too early create coordination overhead, unstable interfaces, empty repos, and release complexity.

## Rollout

1. Start with `recon-core`.
2. Split `recon-adapter-testkit`, `recon-duckdb`, and production adapter
   packages after typed check plans, adapter API versioning, and shared adapter
   tests stabilize. Shared adapter tests must include profile-rendering,
   including unsupported `{{ ... }}`, `{% ... %}`, and `{# ... #}`
   template-fragment rejection, diagnostic-redaction, adapter metadata,
   capability declaration, public/shared rendering helper checks that reject
   missing, malformed, exception-raising, or mismatched renderer `adapter_type`
   before rendering, and empty or malformed renderer output conformance,
   including sanitized adapter factory exceptions, sanitized adapter metadata
   exceptions, sanitized capability declaration exceptions, and short numeric
   rendered-scalar redaction cases such as `port: 12`, `12.0`, `+12`, and
   `1.2e1` across text fields, resource metadata, `rendering.adapter_type`, and
   numeric `line`/`column`, before any split repo claims compatibility.
   They must also include diagnostic-code redaction cases where unsafe config
   keys or rendered values are embedded in delimiter-separated or separatorless
   forms, such as `RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`,
   and `RC12LEAK`, before the test-kit or adapter repos claim compatibility.
   They must also cover malformed factory diagnostic payloads at field level:
   invalid `Diagnostic` severity, code, message, optional context fields, and
   `line`/`column` values must fail as `RC_ADAPTER_RESOLUTION_FAILED` before
   redaction, rendering, artifact writing, or execution consumes them.
   They must also cover parsed DSN component redaction, explicit adapter
   API/renderer `adapter_type` binding before renderer invocation, and rendered
   SQL step `required_capabilities` enforcement before any test-kit or adapter
   repo claims compatibility.
3. Add adapter conformance suites for each compatibility family before any
   adapter repo claims that family:
   - execution placement and comparison-engine behavior,
   - materialization or staging behavior,
   - result/evidence sink writes and production result tables,
   - probabilistic key-summary build, serialization, probe, reverse-probe,
     metrics, privacy, and cleanup.
4. Add official check/policy packages.
5. Add `recon-hub-index`.
6. Add integrations such as `recon-orchestrator`.

## Compatibility claim boundaries

An adapter package can be useful before it is stable, but it must label its
status accurately. Experimental adapters must not claim stable execution,
placement, materialization, sink, result-table, or probabilistic-summary
compatibility until the relevant shared conformance suite exists and passes.

The `recon-duckdb` split follows the same rule as other adapters. It should not
leave `recon-core` as an external package until the shared adapter API,
packaging, conformance tests, and release process are stable enough for another
repository to prove the same behavior.

Result/evidence table sinks through a source, target, or third configured
connection require explicit destination configuration and proven write/sink
capabilities. Adapter availability alone must not imply result-table support.

Probabilistic key-diff support, including Bloom-filter-like summaries and other
set sketches, requires a separate strategy and test-kit conformance before any
adapter claims support. Exact source-target equivalence remains the default
claim unless the result and evidence wording explicitly says otherwise.

## Source of truth

`recon-core` remains the source of truth for product definition, framework concepts, contract syntax, validation rules, ADRs, base interfaces, package rules, and adapter rules.

Other repos should reference `recon-core` rather than redefining the product model.

## Design principle

Build one serious core first, but design for an ecosystem from day one.
