# Ecosystem Roadmap

## Purpose

Recon should start as a focused open-source core and grow into an ecosystem.

The ecosystem should not be created too early, but the core should be designed so it can support adapters, packages, integrations, and Hub later.

## Core repo

`recon-core` remains the source of truth for:

- product model,
- contract schema,
- parse/compile/run behavior,
- artifact model,
- check result model,
- adapter interface,
- package rules,
- validation rules.

## Adapter ecosystem

Long-term adapter packages:

```text
recon-duckdb
recon-postgres
recon-mysql
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

DuckDB currently starts as an in-core local development adapter installed with
`recon-core[duckdb]`. A separate `recon-duckdb` package should wait until the
adapter API and shared adapter test kit stabilize.

Official external adapter repositories are Post-MVP Milestone 29 work. They
should wait for the adapter test-kit and package split milestone that proves
adapter API, capability, rendering, execution, diagnostics, privacy, and
compatibility behavior across repositories. Until that gate is satisfied, the
in-core DuckDB adapter remains a local development adapter and `recon-duckdb`
remains a future extraction candidate.

Adapter packages should own:

- connection,
- SQL dialect,
- metadata access,
- schema introspection,
- type mapping,
- hashing behavior,
- capability declarations.

Adapter packages should not own reconciliation semantics. `recon-core` owns
typed check plans and comparison meaning; adapters render or execute those
plans for a specific system.

Adapter packages should declare their supported adapter API version.

Adapter compatibility claims must be granular. An adapter may support current
rendering without claiming stable execution, broad placement,
materialization/staging, result/evidence sink writes, production result tables,
or probabilistic key-summary behavior.

Production result-table and evidence-sink support through adapters must wait
for Post-MVP Milestone 25.5 result-table/sink design and Post-MVP Milestone 29
adapter write/sink conformance. Source, target, or third-connection
destinations are allowed only when explicitly configured and proven by adapter
capability tests.

Probabilistic key-diff support, including Bloom-filter-like summaries or other
set sketches, must wait for Gate 4K and Post-MVP Milestone 29 adapter test-kit
conformance for summary build, serialization, transport or storage, probing,
reverse probing when needed, metrics, privacy, and cleanup.

Experimental adapters can be useful for learning, but they must not claim
stable execution compatibility, sink compatibility, table-sink compatibility,
or probabilistic-summary compatibility until the relevant conformance gates are
implemented and passing.

## Adapter test kit

Future repo:

```text
recon-adapter-testkit
```

Purpose:

- validate adapter behavior,
- validate adapter API version compatibility,
- standardize capability tests,
- test metadata behavior,
- test SQL rendering for typed plan operations,
- help community adapter maintainers.

Adapter test kit should appear after the typed check-plan and base adapter
interfaces stabilize. Its first compatibility suite must include
the Adapter/Profile Diagnostic Conformance Gate from
`docs/compatibility/adapter-api.md` before external adapter repos are published
or treated as compatible. That conformance must prove that adapter factory
exceptions, capability declaration exceptions, adapter metadata exceptions, and
adapter-provided diagnostics cannot leak rendered profile keys or values into
CLI output, artifacts, run results, evidence, reports, logs, failure details, or
test snapshots. It must include literal adapter `type` routing, including
rejection of templated `{{ ... }}`, `{% ... %}`, `{# ... #}`, or
`env_var(...)` `type` before adapter resolution, plus rejection of
factory-returned adapter metadata that differs from the literal profile `type`,
public/shared rendering helper cases where a supplied renderer's
`adapter_type` is missing, malformed, exception-raising, or different from the
resolved adapter type and therefore fails before rendering,
diagnostic-code cases where unsafe config keys or rendered values are embedded
in delimiter-separated or separatorless forms, such as `RC_PASSWORD_LEAK`,
`RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`, before the shared test
kit or external adapter repos claim compatibility. It must also prove safe
adapter diagnostic codes with incidental non-secret config-key substrings, such
as `RC_ADAPTER_CAPABILITY_UNSUPPORTED`, are preserved.

## Check and policy packages

Future official packages:

```text
recon-checks-cdc
recon-checks-migration
recon-checks-medallion
recon-policies-sampling
recon-policies-tolerances
recon-evidence-templates
```

These packages should provide reusable standards while keeping private project mappings out.

## Schema policy packages

Schema policy packages may provide common technical-column ignore rules.

Examples:

- replication service metadata columns,
- managed ingestion metadata columns,
- change-event metadata columns,
- ingestion audit columns.

These should remain explicit. Installing a package should not silently ignore columns unless a user references the policy.

## Recon Hub

Future repo:

```text
recon-hub-index
```

Initial Hub can be a static index of packages and adapters with metadata.

Possible categories:

- adapter,
- check pack,
- sample policy,
- tolerance policy,
- schema policy,
- evidence template,
- example project,
- domain package.

## Integrations

Future integrations:

```text
recon-orchestrator
recon-workflow-provider
recon-github-action
```

These should come after the CLI and artifacts are stable.

## Documentation site

Docs may eventually move into:

```text
recon-docs
```

Only split docs after the core documentation becomes too large for the core repo.

## Examples repo

Large end-to-end examples may eventually move into:

```text
recon-examples
```

Keep small examples in `recon-core` until the examples become heavy.

## Community contribution path

Community contributors should be able to contribute:

- docs,
- examples,
- checks,
- adapters,
- policy packages,
- evidence templates.

The contribution process should favor small, tested, well-documented changes.

## Ecosystem sequencing

Recommended order:

1. stabilize `recon-core`,
2. stabilize contract schema,
3. stabilize parse/compile/run artifacts,
4. stabilize adapter interface,
5. create adapter test kit,
6. split `recon-duckdb` and official adapters only after adapter conformance
   gates are satisfied,
7. create official check/policy packages,
8. create Hub index,
9. create orchestration integrations.

## Ecosystem principle

Do not create many repos before the core concepts are stable.

Design for the ecosystem early, but split when there is real code, real tests, and real users.
