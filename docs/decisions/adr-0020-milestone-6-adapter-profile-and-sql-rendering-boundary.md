# ADR 0020: Milestone 6 Adapter, Profile, and SQL Rendering Boundary

## Context

Recon Core compiles equivalence contracts into typed check plans. The next
execution-facing step is to render those typed plans through an adapter boundary
without moving reconciliation semantics into database-specific code.

The design must cover:

- connection profiles and secret handling,
- adapter API shape and versioning,
- capability declarations and validation timing,
- compiled SQL artifact paths and rendering status,
- first local development adapter scope,
- query endpoint execution boundaries,
- typed operation catalog expansion policy.

dbt Core and dbt adapters provide the strongest mature reference for profile
selection, adapter boundaries, adapter registration, generated artifacts, and
shared adapter tests. Recon should borrow those boundaries, but not dbt-style
macro dispatch as the primary comparison engine. Recon's public contract is a
typed, inspectable reconciliation plan.

DVT, Soda Core, Great Expectations, and Datafold data-diff provide useful
references for source-target comparison workflows, datasource configuration,
SQL datasource boundaries, and query-based comparison patterns. Their execution
strategies are useful inputs, but Recon must preserve Core-owned comparison
semantics and evidence-oriented artifacts.

## Decision

Milestone 6 will establish the adapter and SQL-rendering foundation. It will
not implement full check execution, run result aggregation, evidence writing,
or production adapter packages.

### Profiles, connections, and secrets

Recon will use an uncommitted profile file for connection configuration:

```text
connections/profiles.yml
```

Example profile shape:

```yaml
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
```

Profile and target selection are environment selection. The selected target
contains named connections. Contract `source.connection` and
`target.connection` values resolve against those connection names.

`recon_project.yml` may select the project profile:

```yaml
profile: local
```

Profile resolution follows these rules:

- Resolve one selected profile and one selected target.
- Treat the selected target as an environment containing named connections.
- Resolve contract `source.connection` and `target.connection` values against
  the selected target's `connections` map.
- For contract-specific adapter rendering or execution, render only the named
  connection payloads referenced by the selected contracts.
- Support `env_var('NAME')` and `env_var('NAME', 'default')` initially for
  non-routing connection config fields.
- Require connection `type` values to be literal non-empty adapter types. The
  `type` field selects the adapter boundary and may appear as public adapter
  metadata, so it does not support `env_var(...)` rendering or any template
  fragments.
- Reject unsupported template fragments in referenced non-routing connection
  config fields before adapter resolution, including `{{ ... }}` expressions,
  `{% ... %}` statements, and `{# ... #}` comments.
- Missing environment variables in referenced connection payloads are errors.
- Missing environment variables in unselected targets and unreferenced
  connections do not fail contract-specific invocations.
- Do not write secrets or fully rendered credential payloads into manifests,
  compiled artifacts, compiled SQL, run results, diagnostics, or evidence.
- Generated artifacts may include profile name, target name, adapter type, and
  non-secret relation identifiers.

Profile loading is required for adapter-aware rendering, execution, future
connection validation, and future debug commands. Plain parse does not need to
load profiles. Compile loads profiles only when adapter-aware rendering or
adapter capability validation is requested.

### Adapter API boundary

Recon will separate the adapter boundary into two concepts:

```text
BaseAdapter
SqlRenderer
```

`BaseAdapter` owns adapter metadata, connection lifecycle, metadata access,
query execution, and adapter capability declarations.

`SqlRenderer` owns dialect-specific rendering of Recon typed check-plan
operations into SQL.

Core owns:

- contract parsing and validation,
- check-pack expansion,
- metric compilation,
- typed check-plan models,
- check requirements and prerequisites,
- result and evidence models,
- required capability semantics,
- diagnostics and public artifact shape.

Adapters own:

- connection lifecycle,
- relation and identifier rendering,
- metadata retrieval,
- dialect SQL rendering,
- execution details,
- type mapping,
- timestamp and hash behavior,
- capability declarations,
- adapter-specific tests.

Adapters must not redefine reconciliation semantics.

### Adapter API versioning

Core will define an adapter API version once the first interface is
implemented. Adapters will declare:

```text
adapter_type
adapter_version
supported_adapter_api_version
capabilities
```

Core must reject incompatible adapter API versions before rendering or
execution with a clear diagnostic.

### Capability support states

Capabilities will use support states rather than booleans:

```text
unknown
unsupported
not_implemented
versioned
full
```

Rules:

- `unknown` never satisfies a required capability.
- `unsupported` means the adapter intentionally does not support the
  capability.
- `not_implemented` means the capability is expected for the adapter but not
  implemented yet.
- `versioned` means support depends on adapter, engine, or database version.
- `full` means the adapter implements and tests the capability.

Compile without an adapter may still produce typed plans with
`rendering.status: not_rendered`.

Adapter-aware rendering must fail validation when a required capability is
`unknown`, `unsupported`, or `not_implemented`. Runtime must revalidate adapter
API version and capabilities before execution.

The initial Milestone 6 adapter-aware scope has two capability layers.
Typed plans continue to require only operation-specific capabilities already
emitted by the compiler:

```text
row_count
aggregate
grouped_aggregate
key_diff
null_key
duplicate_key
```

Relation endpoints also require adapter support for `relations`, but that is a
selected-contract endpoint prerequisite rather than a capability currently
encoded on every emitted typed operation.

SQL rendering may also require renderer capabilities such as common table
expression support and identifier quoting.

### Compiled SQL artifacts

Adapter-rendered SQL belongs under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks should reference rendered SQL artifacts without embedding
connection secrets.

Implementation note, 2026-06-01: compiled-check `rendering.sql_paths` stores
paths relative to the configured `target-path`, for example
`compiled_sql/customer_revenue/check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql`.
Implementation note, 2026-06-02: compiled-check rendering metadata includes
`rendering.adapter_type` when an adapter is known. This is additive traceability
metadata for compiled artifact version 1.

Milestone 6 adapter-aware rendering should migrate rendering status values to:

```text
not_rendered
rendered
blocked
failed
```

Meanings:

- `not_rendered`: adapter-aware rendering was not requested.
- `rendered`: all SQL needed for the check was rendered.
- `blocked`: rendering was intentionally skipped because validation failed.
- `failed`: rendering was attempted but failed because of an adapter or
  rendering error.

Implementation note, 2026-06-05: when `--render-sql` is requested but compile
validation prevents adapter rendering from starting, otherwise renderable checks
use `blocked` with `RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, not
`not_rendered`.

If any check in a `recon compile --render-sql` invocation produces a rendering
diagnostic, the invocation writes no compiled SQL files. Checks with validation
or capability blockers are marked `blocked`, renderer errors are marked
`failed`, and otherwise renderable checks are also marked `blocked` because no
SQL artifact path is available for them. Otherwise renderable checks blocked
only by this invocation-wide SQL output suppression include
`RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED` diagnostics in compiled checks
artifacts.

Implementation note, 2026-06-01: the migration from `deferred` and
`unsupported` to `blocked` and `failed` is complete in code, tests,
compiled-artifact examples, and compatibility docs.

Rendered SQL artifacts must remain traceable to:

- contract name,
- check ID,
- typed operation or rendering step,
- source or target side when applicable,
- adapter type.

Adding rendered SQL references to compiled checks may remain additive for
compiled artifact version 1 when existing field meanings do not change.
Changing existing rendering semantics, paths, stable IDs, or field meanings
requires compatibility review and may require an artifact version bump.

### Local development adapter

The first local development adapter is DuckDB and may live inside `recon-core`
while the adapter API stabilizes. It is installed through the optional
`recon-core[duckdb]` extra while it remains in-core.

DuckDB is selected because it is local, fast, SQL-capable, relation-oriented,
and suitable for golden SQL rendering and early execution tests.

Implementation note, 2026-06-02: Milestone 6 DuckDB SQL rendering blocks source
and target endpoints whose selected profile entries resolve to different
connection configs. The rendered SQL targets one execution context and does not
attach or bridge multiple DuckDB database files. DuckDB aggregate rendering also
rejects `UHUGEINT` metric inputs until exact aggregate behavior for that type is
proven, because current DuckDB returns approximate `DOUBLE` values for
`sum(UHUGEINT)`.

Milestone 6 must not split production adapter packages. Official external
adapter packages, including a future `recon-duckdb`, require a stable adapter
API and shared adapter test kit.

### Query endpoint execution

Milestone 6 is relation-only for executable adapter-aware rendering and
execution.

Authored `source.query` and `target.query` endpoints may remain parseable, but
query endpoints must not become executable in Milestone 6. If adapter-aware
rendering or execution encounters a query endpoint, Recon should produce a
clear diagnostic that executable query endpoints are not implemented.

Executable query endpoints require a later decision covering:

- SELECT-only behavior,
- single-statement requirements,
- semicolon and comment handling,
- wrapping as comparable subqueries,
- query text visibility in artifacts and evidence,
- adapter capability requirements,
- dialect-specific limitations.

### Typed operation catalog

Milestone 6 must not expand the typed operation catalog.

Adapters should render only operations already emitted by the current compiler.
Placeholder operations such as `null_safe_equal`, `cast`, `limit`, `hash`,
`timestamp_diff`, and `schema_metadata` remain non-emittable until their payload
schemas, capability mappings, renderer tests, and compatibility docs are
updated together.

Adding or changing a typed operation is a public adapter and typed-plan change.

### Comparison execution placement

Milestone 6 renders SQL. It does not decide every future execution placement
strategy.

Before check-engine execution, Recon must define where comparison work may run:

- source system,
- target system,
- adapter-managed intermediate system such as DuckDB,
- bounded Python-side comparison inside Recon Core.

The first check-engine implementation must not silently fall back to Python for
unsupported SQL behavior. Any Python or intermediate-system fallback requires
explicit limits, diagnostics, privacy rules, result semantics, and evidence
visibility.

## Alternatives Considered

### Keep adapter capabilities as booleans

Rejected.

Boolean capabilities cannot distinguish unknown support from explicitly
unsupported behavior or version-dependent support. Recon needs conservative
capability validation so unsupported checks do not look executable.

### Put DuckDB in a separate repository immediately

Rejected for Milestone 6.

The adapter API and shared adapter tests are not stable yet. Splitting an
adapter too early would freeze an immature public API or allow behavior to
drift from Core-owned semantics.

### Execute query endpoints in the first adapter milestone

Rejected for Milestone 6.

Running user-authored SQL is a safety and public behavior boundary. Relation
execution is sufficient to prove adapter API, capability validation, compiled
SQL rendering, and the first local adapter.

### Let adapters choose comparison strategy independently

Rejected.

Adapters can choose dialect rendering and execution mechanics, but Core must
own the semantic strategy. Otherwise the same contract could mean different
things on different adapters.

### Use Python fallback whenever SQL rendering is unsupported

Rejected as an implicit behavior.

Python-side comparison can move sensitive data, exceed local memory, and weaken
evidence if it is not explicitly bounded. Unsupported rendering should produce
a clear diagnostic until a fallback strategy is designed.

## Consequences

- Milestone 6 can proceed after the profile, adapter, capability, compiled SQL,
  and relation-only query boundary docs are aligned.
- Adapter-aware compile/rendering can be built without implementing full
  `recon run`.
- DuckDB can prove the adapter boundary inside `recon-core` before adapter
  repositories split.
- Production adapter packages remain gated by adapter API stability and a
  shared adapter test kit.
- Check execution placement remains a required decision before Milestone 7.

## Implementation Guidance

Milestone 6 implementation should add tests before code for:

- profile selection, selected-target resolution, and referenced named
  connection environment rendering,
- missing environment variables in referenced connection payloads,
- ignored environment variables in unselected targets and unreferenced
  connections for contract-specific invocations,
- secret redaction from diagnostics and generated artifacts,
- adapter diagnostic-code redaction for unsafe config keys and rendered profile
  values in delimiter-separated and separatorless forms, including examples such
  as `RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and
  `RC12LEAK`,
- adapter API version compatibility,
- adapter registry resolution by connection type, including malformed factory
  results and malformed factory diagnostic payloads as
  `RC_ADAPTER_RESOLUTION_FAILED`; malformed diagnostic payloads include
  invalid `Diagnostic` field values such as string severities, empty or
  non-string `code` or `message`, non-string optional context fields, and
  non-integer `line` or `column` values,
- relation-endpoint support validation for selected contracts,
- capability support-state validation for operation-specific requirements,
- DuckDB renderer capability declarations,
- SQL rendering for currently emitted operations only,
- compiled SQL artifact path safety and traceability,
- relation-only diagnostics for query endpoints,
- rendering status migration from draft `deferred`/`unsupported` values to
  `blocked`/`failed` values.

The implementation should not:

- execute checks end to end,
- write run results,
- write evidence reports,
- add production adapter repositories,
- expand typed operation payloads,
- make query endpoints executable,
- add silent Python comparison fallback.

## References

- dbt adapter creation: `https://docs.getdbt.com/guides/adapter-creation`
- dbt adapter object: `https://docs.getdbt.com/reference/dbt-jinja-functions/adapter`
- dbt adapters: `https://github.com/dbt-labs/dbt-adapters`
- DVT: `https://github.com/GoogleCloudPlatform/professional-services-data-validator`
- Soda Core: `https://github.com/sodadata/soda-core`
- Great Expectations: `https://github.com/great-expectations/great_expectations`
- Datafold data-diff: `https://github.com/datafold/data-diff`
