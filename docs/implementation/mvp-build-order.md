# MVP Build Order

## Purpose

This document defines a practical implementation order for the first working Recon Core.

The goal is to avoid building too many advanced features before the core loop works.

## Milestone 1: package skeleton and CLI

Build:

- Python package skeleton,
- `recon --version`,
- `recon init`,
- command service structure,
- basic diagnostics model.

Tests:

- CLI imports,
- version command,
- init creates expected files.

## Milestone 2: project loading

Build:

- project root discovery,
- `recon_project.yml` loader,
- path resolution,
- profile file discovery,
- generated path defaults.

Tests:

- project root from subdirectory,
- missing project config error,
- default paths,
- invalid config diagnostics.

## Milestone 3: parser and manifest

Build:

- YAML loader,
- contract parser,
- multi-contract file support if simple,
- resource discovery,
- duplicate contract detection,
- `target/manifest.json`.

Tests:

- valid contract parse,
- invalid YAML,
- missing required fields,
- duplicate names,
- manifest shape.

## Milestone 4: compiler foundation

Build:

- compiled contract model,
- compiled check model,
- typed check plan model,
- stable compiled IDs,
- top-level compiled artifact headers with invocation IDs,
- default resolution,
- metric compilation,
- check-pack expansion for `basic_equivalence`,
- adapter capability requirements,
- identity and check requirement metadata,
- compiled artifact writers.

Tests:

- stable ID helpers,
- compiled model serialization,
- metric compiles to aggregate check,
- check pack expands,
- `basic_equivalence` without grain fails validation,
- compiled checks lower into typed plan operations,
- empty check-pack expansion errors,
- compiled YAML artifacts match expected output.

## Milestone 4.5: shared parsed-project loading

Build this hardening milestone before Milestone 5.

Goal:

- keep authored project files as the source of truth,
- keep `target/manifest.json` as a generated machine-oriented artifact,
- remove duplicated contract discovery/loading/parsing flow between parse and
  compile services before the validation rulebook expands,
- avoid introducing manifest freshness or caching behavior yet.

Build:

- shared internal parsed-project loading helper used by both `ParseService` and
  `CompileService`,
- a typed return model containing project context, discovered resource files,
  parsed contracts, and parse diagnostics,
- parse behavior that still writes `target/manifest.json`, including parse
  diagnostics when structural validation fails,
- compile behavior that still stops before compiled artifact writing when parse
  diagnostics exist,
- no public CLI behavior change,
- no generated artifact format change,
- no requirement for `recon compile` to read `target/manifest.json`.

Tests:

- parse and compile use the same shared parser pipeline,
- parse still writes a manifest with diagnostics for invalid authored
  resources,
- compile still writes no compiled artifacts when parse diagnostics exist,
- compile still succeeds for valid projects without requiring a pre-existing
  manifest,
- project configuration errors still prevent both manifest and compiled artifact
  writes.

Required gate:

- resolve the local resource loading and precedence gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` before
  expanding this milestone beyond contract-resource loading.

Recommended commit message:

```text
refactor: share parsed project loading across services
```

## Milestone 4.6: non-contract resource discovery and indexing

Status:

- implemented for local source-file indexing,
- not implemented for parsed local resource schemas, reference validation,
  endpoint resources, packages, or macro semantics.

Build this only after Milestone 4.5 is complete and only if Milestone 5 needs
validated references to local non-contract resources.

Goal:

- discover non-contract project resources through the shared parsed-project
  loading pipeline,
- keep one source of truth for parse and compile resource visibility,
- record resource files, paths, namespaces, source locations, and checksums,
- avoid parsing or executing resources whose semantics are not implemented yet.

Build:

- catalog entries for supported non-contract resource kinds,
- optional default path behavior and explicit missing-path diagnostics from ADR
  0017,
- deterministic discovery and checksum metadata,
- manifest `files` entries for local non-contract source files using the
  existing file-record shape,
- macro file discovery and checksumming as source files only.

The first implementation should index these local resource kinds:

- `check_pack`,
- `sample_policy`,
- `tolerance_policy`,
- `schema_policy`,
- `macro_file`.

It should continue to parse only `contract` files. Duplicate resource-name
validation, local resource reference validation, and parsed resource summaries
belong to the milestone that implements each resource kind's schema and
semantics.

Do not build:

- endpoint resource loading,
- package resource loading,
- parsed local check-pack or policy resource models,
- local check-pack or policy reference validation,
- macro parsing,
- macro rendering,
- macro execution,
- macro reference validation,
- package macro loading.

Tests:

- default optional resource paths may be absent,
- explicitly configured optional resource paths fail when missing,
- resource discovery is deterministic,
- checksums are stable,
- macro files are discovered only as source files and do not create executable
  behavior.

Required gates:

- resolve the local resource loading and precedence gate,
- resolve the macro discovery and indexing gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: index non-contract project resources
```

## Milestone 5: validation rulebook

Build:

- row-level check validation requires keys for supported row-level checks,
- CDC propagation validation requires CDC keys only for supported CDC checks,
- columns do not create checks,
- typed authored column declarations are validated without physical adapter
  metadata,
- metric value and group-by references are validated against the declared
  column surface when one exists,
- duplicate metric names and duplicate same-pack invocations fail validation,
- no silent all-column comparison,
- wildcard column selectors are rejected or deferred until adapter metadata can
  resolve them into explicit columns,
- incompatible check/column type combinations fail validation for supported
  current checks and metrics,
- contract-level sampling `default_policy` stays limited to `full` or a
  non-empty named policy reference until policy resources are loaded,
- MVP tolerance/null/normalization validation applies only to accepted current
  surfaces,
- named local policy references are preserved but not resolved until typed
  resource loading exists.

Required gates:

- validation timing and diagnostic code catalog gate is satisfied by
  `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`,
- local resource loading and precedence design gate is satisfied by
  `docs/decisions/adr-0017-project-resource-loading-and-precedence.md`, but
  actual reference validation still requires the relevant resource loader to be
  implemented,
- macro discovery/indexing, if included before Milestone 5, is source-file
  metadata only; Milestone 5 must not validate, parse, render, or execute macro
  references,
- check-pack invocation config and override design is satisfied by
  `docs/decisions/adr-0018-check-pack-invocation-config.md`; supporting
  `config`, `on_empty: warn`, or `on_empty: skip` still requires implementation
  of typed invocation models, schema validation, and artifact visibility,
- column model and value-comparison surface design is satisfied by
  `docs/decisions/adr-0019-column-and-value-comparison-surface.md`; supporting
  resolved column metadata, all-column expansion, column-level check
  eligibility, unused declared-column warnings, adapter metadata validation, or
  row-level value checks still requires implementation of the relevant typed
  models, metadata validation, and artifact visibility,
- tolerance, null, and normalization resolution design is satisfied by
  `docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`;
  Milestone 5 should validate only the MVP policy surface and must not treat
  future timestamp, relative tolerance, reusable policy files, unrestricted
  regex features, custom SQL, or macros as executable behavior,
- top-level contract `normalization` remains unsupported in this milestone;
  accepting contract-level normalization defaults requires the local policy
  defaults gate to be resolved first,
- compiled policy artifact alignment must be additive: preserve
  `policies.tolerance_policy` as the authored named reference, expose accepted
  `nulls`, and do not rename or change existing policy field meanings without
  compatibility review,
- do not resolve or validate references to local/package check-pack resources,
  sampling policies, tolerance policies, schema policies, endpoint resources,
  or macros until those resource kinds are loaded through the shared ADR 0017
  resource model. Unsupported built-in check-pack names still fail validation
  instead of compiling as silent no-ops.

Tests:

- each locked validation rule has passing and failing tests.
- future sampling, tolerance, column, check-pack config, and resource-reference
  validation expansions must reuse ADR 0016 phase ownership/code-family rules
  and lock their rule-specific diagnostics before implementation.

## Milestone 6: local/dev adapter

Build:

- base adapter interface,
- adapter API version declaration,
- profile loading for the selected profile and target,
- environment variable rendering for named connections referenced by selected
  contracts inside the selected target,
- local DuckDB development adapter inside `recon-core`,
- relation metadata,
- capability declarations,
- SQL rendering for typed plan operations,
- compiled SQL artifacts under `target/compiled_sql/`,
- first internal adapter test-kit shape.

Current status:

- implemented through adapter-aware compile and SQL rendering,
- DuckDB remains in-core behind `recon-core[duckdb]`,
- current DuckDB support renders SQL for existing typed plans only,
- connection lifecycle, metadata fetches, row-count query execution, check
  execution, run results, and evidence remain future milestones.

Required gates:

- resolve the profiles, connections, secrets, and adapter diagnostic redaction
  gate before adapter execution,
- resolve the adapter API, capability validation, and compiled SQL gate before
  implementing the adapter API or SQL rendering,
- resolve the typed operation catalog expansion gate before rendering or
  emitting additional typed operations,
- keep Milestone 6 relation-only; resolve the query endpoint support boundary
  gate only if executable query endpoints are moved into scope,
- do not split `recon-duckdb` into an external package during Milestone 6.

Current pre-implementation alignment:

- `recon init` already writes the ADR 0020 selected profile/target shape with
  named `legacy` and `warehouse` connections in
  `connections/profiles.yml.example`.

Tests:

- selected profile and target loading,
- selected target and referenced named-connection env var rendering,
- unsupported profile template syntax fails for referenced connections,
- secret redaction from diagnostics and artifacts,
- profile-backed adapter diagnostics, including adapter factory, adapter API
  compatibility, and render-phase diagnostics, do not leak rendered connection
  config keys or values,
- profile-backed adapter diagnostics suppress case-changed rendered config keys
  or values, non-string rendered values, unsafe `rendering.adapter_type`
  metadata, numeric `line`/`column` fields, short numeric rendered scalars such
  as port values, integer-equivalent formatted variants such as `12.0`, `+12`,
  and `1.2e1`, and other simple secret transformations,
- typed operation rendering,
- adapter API version compatibility,
- adapter capability support-state validation,
- compiled SQL artifact path and traceability tests,
- unsupported query endpoint diagnostics for adapter-aware rendering.
- adapter setup failures produce blocked compiled-check metadata, write no
  compiled SQL, preserve diagnostics when factories return both adapters and
  diagnostics, de-duplicate repeated same-connection setup diagnostics, and keep
  distinct source/target connection setup diagnostics visible in service output.
- compile validation failures that prevent a requested adapter rendering phase
  from starting still mark otherwise renderable checks `blocked` with
  `RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` and do not invoke
  adapter factories or renderers.

## Milestone 7: check engine

Build:

- check registry,
- row count check,
- duplicate key checks,
- null key checks,
- missing/extra key checks,
- metric sum diff,
- check result model.

Required gates:

- resolve the profile-rendering and adapter diagnostic redaction conformance
  gate before loading rendered profiles or resolving adapters for execution,
- require adapter/profile diagnostic redaction conformance to cover unsafe
  rendered profile keys or values independently in diagnostic code, message,
  hint, path, `resource_type`, `resource_name`, `line`, `column`, and future
  structured diagnostic fields, including short numeric rendered scalars such as
  port values and equivalent formatted variants such as `12.0`, `+12`, and
  `1.2e1`,
- resolve the diagnostic output message conformance gate before runtime
  adapter/profile diagnostics can become check-engine output,
- resolve the source/target data privacy, evidence, and failure-detail policy
  gate before check execution can emit source/target values, runtime adapter
  errors, database errors, or data-derived values through terminal output,
  diagnostics, logs, run results, evidence, or adapter test-kit snapshots,
- preserve the adapter-aware compile contract that setup failures write no SQL,
  mark affected compiled checks blocked, preserve factory diagnostics even when
  an adapter is also returned, de-duplicate repeated same-connection setup
  diagnostics, and keep distinct source/target connection setup diagnostics
  visible before adapter execution surfaces these diagnostics at run time,
- resolve the explicit authored checks and check registry gate before
  implementing explicit `checks: [...]` support or registry behavior that must
  serve explicit checks later,
- resolve the comparison execution placement strategy gate before executing
  typed plans,
- re-check the typed operation catalog expansion gate before executing any
  operation beyond the current compiled subset.

Tests:

- pass/fail cases,
- duplicate keys block row-level checks,
- null keys block row-level checks,
- aggregate metric result,
- check result serialization,
- check-engine diagnostics preserve code, severity, message, path, resource
  context, and hint where available,
- check-engine public output does not leak raw source/target values unless the
  source/target data privacy policy explicitly allows that output.

## Milestone 8: runner and results

Build:

- execution plan,
- run service,
- `target/run_results.json`,
- exit code mapping,
- terminal summary.

Required gate:

- resolve the diagnostic output message conformance gate before locking run
  result diagnostics, exit-code diagnostics, or terminal summary behavior.
- resolve the source/target data privacy, evidence, and failure-detail policy
  gate before writing `target/run_results.json`, terminal summaries, runtime
  diagnostics, or logs that can include source/target values, relation names,
  query text, adapter runtime errors, or database error text.
- resolve the generated artifact lifecycle and cleanup gate before writing
  `target/run_results.json`.

Tests:

- successful run,
- failing check run,
- runtime error,
- exit code mapping,
- run results and terminal output preserve diagnostic code and message for
  runtime, adapter, prerequisite, and result-write failures,
- run results and terminal output follow source/target data privacy defaults for
  raw rows, keys, values, aggregates, relation names, query text, and runtime
  error text.

## Milestone 9: evidence

Build:

- failure detail writer,
- simple report writer,
- artifact references,
- sampling scope in evidence.

Required gate:

- resolve the diagnostic output message conformance gate before evidence,
  report, or failure-detail diagnostics become user-facing output.
- resolve the source/target data privacy, evidence, and failure-detail policy
  gate before writing failure details, reports, evidence, or failure links that
  can expose raw rows, comparison keys, normalized values, aggregate values,
  row counts, relation names, query text, adapter errors, or database errors.
- resolve the generated artifact lifecycle and cleanup gate before writing
  failure details, reports, or evidence artifacts.

Tests:

- failure CSV written,
- report generated,
- row limit respected,
- artifact paths in run results,
- evidence and report diagnostics preserve safe actionable messages instead of
  emitting only diagnostic codes or hints,
- failure details, reports, and evidence follow source/target data privacy
  defaults for raw-value export, masking/redaction, truncation, and generated
  artifact references.

## Milestone 10: examples and docs alignment

Build:

- runnable example project,
- README command verification,
- quickstart alignment,
- known limitations.

Tests:

- examples parse,
- examples compile,
- examples run with local/dev adapter.

## After Milestone 10

Milestones 1-10 complete the MVP build sequence.

After Milestone 10, run the MVP acceptance criteria and release-readiness
checklist before any 0.1 version bump, tag, or publish step.

Do not start treating roadmap work as 0.2 scope until the 0.1 release decision
has been made.

The post-MVP milestones below are concrete capability homes and gate anchors.
Before starting a post-MVP milestone, reconcile the requested capability with
`docs/planning/roadmap.md` and update this build-order document if a capability
must be pulled earlier, delayed, or split.

## Post-MVP Milestone 10.5: artifact freshness and cache optimization

Build this only after Milestones 1-10 are complete and after the 0.1
release-readiness decision.

Goal:

- avoid stale generated artifacts without making hidden cache behavior a source
  of misleading evidence.

Build:

- artifact freshness model for manifest, compiled artifacts, compiled SQL, run
  results, and evidence,
- generated artifact cleanup and publish-ordering rules for stale, partial, and
  orphaned outputs across generated artifact families,
- cache/invalidation keys based on authored files, project config, relevant
  resource checksums, command options, and adapter-capability inputs,
- stale-artifact diagnostics and safe fallback behavior,
- optional skip-unchanged behavior that is visible in terminal output and
  machine-readable artifacts,
- compatibility rules for any freshness metadata added to generated artifacts.

Required gate:

- resolve the generated artifact lifecycle and cleanup gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`,
- resolve the artifact freshness and cache optimization gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add artifact freshness checks
```

## Post-MVP Milestone 11: aggregate metrics expansion

Build this after Milestones 1-10 are complete and after the 0.1
release-readiness decision.

Goal:

- expand explicit aggregate metric support beyond the MVP `sum` metric,
- keep `recon_core.aggregate_equivalence` deferred until its behavior is
  explicitly designed,
- avoid aggregate inference from numeric columns unless a durable decision
  defines the opt-in model and compiled artifact visibility.

Build:

- explicit `min`, `max`, `avg`, and `count_distinct` metric compilation,
- grouped aggregate behavior where adapter capabilities support it,
- validation for metric type and referenced column compatibility,
- typed check-plan operations and adapter capability expectations,
- check-engine execution for the new aggregate metric checks,
- result and evidence fields for aggregate metric comparisons.

Tests:

- each supported metric type compiles into the expected typed plan,
- unsupported metric types produce diagnostics,
- grouped and ungrouped aggregate behavior is covered separately,
- adapter capability validation blocks unsupported aggregate operations,
- run results and evidence preserve metric names and aggregate details.

Required gate:

- resolve the aggregate metrics expansion gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` before
  implementation.

Recommended commit message:

```text
feat: expand aggregate metric checks
```

## Post-MVP Milestone 12: schema policy and metadata checks

Build this after the adapter API and metadata model exist.

Goal:

- implement schema policy checks without silent ignores,
- use adapter-normalized metadata for structural compatibility,
- make ignored columns and schema assumptions visible in results and evidence.

Build:

- `column_presence`,
- `type_compatibility`,
- `nullable_compatibility`,
- `precision_scale_compatibility`,
- schema ignore lists and patterns,
- adapter metadata validation,
- schema check results and evidence fields.

Tests:

- source and target ignore rules are side-specific,
- pattern matching is predictable,
- incompatible types fail or warn according to policy,
- nullable and precision/scale behavior is covered,
- unavailable metadata produces clear diagnostics.

Required gate:

- resolve the schema policy and metadata checks gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` before
  implementation.

Recommended commit message:

```text
feat: add schema policy checks
```

## Post-MVP Milestone 13: explicit source-target column mapping

Build this after the adapter metadata model, resolved column artifacts, schema
policy behavior, run results, and evidence model are stable enough to show
exactly which source and target columns were compared.

Goal:

- support real projects where comparable source and target fields have
  different names,
- keep every mapping explicit in authored config and generated artifacts,
- avoid inferred, fuzzy, or silent source-target mapping.

Build:

- authored YAML shape for explicit source-target column mappings,
- resolved column model fields for canonical, source, and target column names,
- validation for mapped value-check columns and mapped key columns when the
  mapping design includes keys,
- interaction with check-level column selection, `columns.include: "*"`, schema
  policies, ignored columns, adapter metadata, and type compatibility,
- typed check-plan, result, failure-detail, and evidence visibility for mapped
  column names.

Tests:

- same-name MVP behavior remains unchanged,
- missing, duplicate, ambiguous, or undeclared mappings produce diagnostics,
- mapped columns resolve consistently across compiler, typed plans, adapter
  calls, results, and evidence,
- all-column expansion never guesses renamed columns,
- schema/type validation uses the explicit mapping and reports both sides.

Required gate:

- resolve the source-target column mapping gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` before
  implementation.

Recommended commit message:

```text
feat: add explicit source-target column mapping
```

## Post-MVP Milestone 14: macro reference semantics and validation

Build this only after the MVP release-readiness decision and after the resource
loader can index macro files without executing them.

Goal:

- decide whether Recon contracts may reference macros at all,
- define the public YAML surfaces where macro references are allowed,
- validate macro references without making macros the comparison engine.

Build:

- a macro-semantics ADR before implementation,
- authored reference syntax and namespace rules,
- argument and type rules for allowed macro references,
- diagnostics for unknown, ambiguous, unsupported, or invalid macro references,
- compiled artifact visibility for any accepted macro reference,
- tests that prove unsupported macro references fail clearly.

Do not build:

- macro rendering,
- macro execution,
- dbt-style macro dispatch as the primary comparison engine,
- arbitrary custom SQL behavior hidden behind macro names.

Required gate:

- resolve the macro reference semantics gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: validate macro references
```

## Post-MVP Milestone 15: macro-assisted rendering helpers

Build this only after adapter APIs, typed plans, compiled SQL artifacts, run
results, and evidence semantics are stable enough to show exactly what will
run.

Goal:

- allow limited macro or template helpers only as implementation details for
  rendering typed plans,
- keep reconciliation semantics in core-owned typed check plans and validation,
- keep rendered SQL and evidence inspectable.

Build:

- a macro execution/rendering ADR or ADR 0013 update,
- execution/rendering boundary rules,
- deterministic rendering and sandbox/security restrictions,
- adapter capability and adapter test-kit expectations,
- compiled SQL, result, and evidence visibility for rendered behavior,
- diagnostics for rendering failures and unsupported macro helper features.

Do not build:

- macros that define checks or reconciliation semantics,
- side-effectful macro execution,
- hidden adapter behavior that bypasses typed check plans.

Required gate:

- resolve the macro execution and rendering boundary gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add macro-assisted SQL rendering
```

## Post-MVP Milestone 15.5: check-pack invocation config and controls

Build this after the validation rulebook enforces current strict invocation
behavior and before local/package check-pack resources become executable.

Goal:

- support built-in check-pack invocation configuration without silently
  changing generated checks,
- make `on_empty: warn` and `on_empty: skip` visible and safe,
- establish the invocation config rules that package check packs must follow
  later.

Build:

- typed check-pack invocation model for `name`, `on_empty`, and `config`,
- built-in check-pack config schema validation,
- pack-wide severity, sampling, tolerance, null, normalization, params, and
  per-generated-check override validation where supported,
- artifact visibility for invocation summaries and resolved generated-check
  config,
- diagnostics for unknown invocation keys, unknown config keys, unknown params,
  unsupported generated-check names, and unsafe empty expansions.

Do not build:

- local custom check-pack resource schemas,
- package-provided check packs,
- invocation aliases,
- config that bypasses key, CDC, adapter capability, or schema safety checks.

Required design lock:

- complete ADR 0018 artifact-visibility, diagnostics, and resolved-config
  requirements for check-pack invocation summaries before implementation.

Recommended commit message:

```text
feat: add check-pack invocation config
```

## Post-MVP Milestone 16: local and package resource loading

Build this only after local resource schemas and package/dependency behavior
are designed and after ADR 0017 resource indexing is stable.

Goal:

- implement local custom check-pack and reusable policy resources through the
  shared resource catalog,
- load package-provided resources through the same resource catalog as local
  resources,
- keep package namespaces explicit and compatibility ranges documented,
- allow package macro files only under the macro semantics already locked by
  Milestones 14 and 15.

Build:

- local custom check-pack file schema, validation, expansion behavior, and
  compiled artifact visibility,
- local sampling, tolerance, and schema policy file schemas plus reference
  resolution when the relevant execution engine exists,
- package/dependency model and lock-file behavior,
- package resource schema and compatibility range validation,
- package namespace validation,
- package resource discovery for check packs, policies, and macro files,
- compatibility documentation for package resource schemas and macro behavior.

Do not build:

- package macros that override local or `recon_core` behavior by search
  precedence,
- package macro execution before macro execution semantics are locked.

Required gate:

- resolve the local custom check-pack resource semantics gate,
- resolve the reusable local policy file resources gate,
- resolve the packages, deps, and package macro resources gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: load reusable project resources
```

## Post-MVP Milestone 16.5: package dependency installer and lock workflow

Build this only after local/package resource loading semantics are stable
enough that installed packages have a meaningful resource model.

Goal:

- implement `recon deps` without making package installation, updates, or lock
  files a hidden source of resource behavior.

Build:

- `packages.yml` schema,
- dependency resolution and install/update behavior,
- package lock file shape and compatibility expectations,
- supported package sources such as registry, git, or local path,
- install path rules for `recon_packages/`,
- checksum, version, and namespace validation,
- diagnostics for unsupported sources, conflicting packages, invalid locks, and
  unsafe updates.

Required gate:

- resolve the package dependency installer and lock workflow gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add package dependency installer
```

## Post-MVP Milestone 17: endpoint resources and endpoint references

Build this after relation-based contracts and the shared resource loader are
stable.

Goal:

- let contracts reuse named local endpoints without hiding source or target
  assumptions,
- keep endpoint references explicit in authored YAML and compiled artifacts,
- keep endpoint resources local-only until package endpoint semantics are
  separately designed.

Build:

- `endpoint-paths` project config if still needed,
- endpoint resource schema,
- endpoint reference syntax and resolution,
- validation for missing, duplicate, or ambiguous endpoint references,
- compiled artifact visibility for resolved relation/query endpoint fields.

Required gate:

- resolve the endpoint resources and references gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add endpoint resource references
```

## Post-MVP Milestone 18: executable query endpoints

Build this after adapter query execution boundaries and compiled SQL visibility
are locked.

Goal:

- run contracts whose source or target is an authored SQL query,
- keep query wrapping, safety, capabilities, artifacts, results, and evidence
  explicit.

Build:

- query endpoint execution through adapters,
- query safety validation,
- query wrapping rules for comparison subqueries,
- adapter capabilities for query metadata and execution,
- compiled SQL and evidence visibility for query-based checks.

Required gate:

- resolve the query endpoint support boundary gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.
- resolve the generated artifact lifecycle and cleanup gate if query endpoint
  execution writes query-specific compiled SQL, results, evidence, or debug
  artifacts.

Recommended commit message:

```text
feat: execute query endpoints
```

## Post-MVP Milestone 19: selectors and subset execution

Build this after manifest metadata and run result scope fields can accurately
describe partial work.

Goal:

- support `--select`, `--exclude`, and `selectors.yml` without producing
  misleading partial artifacts or evidence.

Build:

- selector syntax and named selector schema,
- contract and optional check selection semantics,
- partial compile/run behavior,
- selected-scope metadata in artifacts and run results,
- diagnostics for empty or invalid selections.

Required gate:

- resolve the selectors and contract selection semantics gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.
- resolve the generated artifact lifecycle and cleanup gate before selector
  compile/run writes partial or scoped generated artifacts.

Recommended commit message:

```text
feat: add contract selectors
```

## Post-MVP Milestone 20: defaults and inheritance boundaries

Build this after project loading, compiled artifact provenance, and validation
timing can show where inherited behavior came from.

Goal:

- support project/file defaults safely,
- keep deep inheritance and template behavior out until explicitly designed.

Build:

- resolved default precedence for supported contract fields,
- artifact provenance for inherited defaults,
- validation for unsupported deep inheritance or template syntax,
- tests proving authored behavior is not silently changed by hidden defaults.

Required gate:

- resolve the defaults, inheritance, and template boundary gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: resolve authored defaults
```

## Post-MVP Milestone 21: row-level value check execution

Build this after column resolution, tolerance/null/normalization resolution,
adapter metadata, and key safety checks are executable.

Goal:

- execute exact and numeric row-level comparisons without guessing keys,
  columns, types, or normalization behavior.

Build:

- `exact_value_match`,
- `numeric_tolerance_match`,
- prerequisite blocking for null/duplicate keys,
- resolved column and policy payloads in typed plans,
- result, failure-detail, and evidence output for value mismatches.

Required gate:

- resolve the row-level value check execution gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: execute row-level value checks
```

## Post-MVP Milestone 22: timestamp tolerance and timezone execution

Build this after adapters can expose timestamp metadata and render timestamp
operations safely.

Goal:

- compare timestamp/date/time values only when units, timezone behavior,
  metadata, adapter capabilities, results, and evidence are explicit.

Build:

- timestamp tolerance policy execution,
- timezone policy validation,
- typed timestamp-diff payloads,
- adapter capability and test expectations,
- result and evidence fields for timestamp comparisons.

Required gate:

- resolve the timestamp tolerance and timezone execution gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: execute timestamp tolerance checks
```

## Post-MVP Milestone 23: row hash and canonical hash comparison

Build this only after hash canonicalization and adapter compatibility are
designed.

Goal:

- support row hash comparison without assuming cross-database hash equality.

Build:

- canonical row-hash payload design,
- adapter capability and compatibility rules,
- typed hash operations,
- diagnostics for unsafe cross-system hash comparisons,
- result and evidence visibility for hash inputs and assumptions.

Required gate:

- resolve the row hash and canonical hash comparison gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add safe row hash checks
```

## Post-MVP Milestone 24: sampling execution modes

Build this after sampling policy resolution, adapter capability requirements,
and evidence fields are locked for each mode.

Goal:

- execute sampled checks without allowing independent source and target samples
  to look comparable.

Build:

- deterministic numeric modulo sampling where valid,
- deterministic hash sampling only when portable behavior is proven,
- explicit anchor-side semantics,
- sampled check artifact and evidence visibility,
- future mode diagnostics for random, previous-failure, stratified, and
  high-value samples until their state requirements are implemented.

Required gate:

- resolve the sampling execution modes gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: execute deterministic sampling policies
```

## Post-MVP Milestone 24.5: multi-policy sampling composition

Build this after individual sampling modes, sample-key references, state
behavior, and evidence fields are stable enough to show exactly which records
were checked.

Goal:

- allow a contract or check to combine multiple explicit sampling policies
  without losing reproducibility or overstating coverage.

Build:

- authored YAML shape for multiple sampling policies,
- composition semantics such as union, intersection, ordering, deduplication,
  and per-check narrowing,
- validation for incompatible sampling modes and unsafe independent source/target
  samples,
- compiled artifact, run result, state, and evidence visibility for each policy
  and the combined selected scope.

Required gate:

- resolve the multi-policy sampling composition gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: compose sampling policies
```

## Post-MVP Milestone 25: state, watermarks, and persisted samples

Build this after run lifecycle, result semantics, and local artifact storage
rules are stable.

Goal:

- make recurring validation reproducible through explicit state and safe
  watermark advancement.

Build:

- local state backend shape,
- local state artifact format,
- watermark bootstrap and advancement rules,
- persisted sample-key records,
- previous-failure key records,
- compatibility/versioning rules for state formats.

Do not build:

- remote or database-backed state before Post-MVP Milestone 37 locks storage,
  locking, migration, and credential behavior.

Required gate:

- resolve the state, watermarks, and persisted samples gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add local reconciliation state
```

## Post-MVP Milestone 25.5: production result tables

Build this after run result semantics, basic evidence, local state shape, and
profile/adapter execution boundaries are stable.

Goal:

- make recurring runs queryable by production workflows without mixing result,
  evidence, and state semantics.

Build:

- result table writer design and implementation,
- table schema/versioning and migration rules,
- write modes, retention, idempotency, and retry behavior,
- adapter/profile requirements and credential-safe diagnostics,
- links between result tables, `run_results.json`, evidence artifacts, failure
  details, and state records,
- privacy rules for sensitive values written to tables.

Required gate:

- resolve the result table writer gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add production result tables
```

## Post-MVP Milestone 26: first CDC implementation

Build this after state/window behavior, CDC key semantics, adapter execution,
run results, and evidence can explain CDC scope.

Goal:

- implement the first narrow CDC path without assuming all CDC tools behave the
  same way.

Build:

- first supported CDC mode and window model,
- freshness lag,
- latest window count,
- incremental key coverage,
- explicit `cdc.keys` validation,
- resolved CDC identity artifact shape, if CDC checks need resolved identity
  fields instead of the current authored CDC policy snapshot,
- CDC result and evidence fields.

Required gate:

- resolve the CDC first implementation scope gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add first CDC checks
```

## Post-MVP Milestone 27: asymmetric CDC delete representation

Build this only after the first CDC implementation exists and delete behavior
needs to support different source and target representations.

Goal:

- model source hard delete, source soft delete, target soft delete, and
  operation-column delete behavior without one-size-fits-all assumptions.

Build:

- side-specific delete representation syntax,
- validation for supported and unsupported combinations,
- compiled artifact fields for both sides,
- delete propagation result and evidence fields.

Required gate:

- resolve the asymmetric CDC delete representation gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add asymmetric CDC delete checks
```

## Post-MVP Milestone 27.5: advanced CDC modes and propagation checks

Build this after the first CDC implementation and delete representation rules
are stable enough that advanced CDC checks can report exactly which movement
patterns they validate.

Goal:

- expand CDC beyond the first narrow path without turning all CDC systems into
  one implicit model.

Build:

- operation-column CDC mode and operation mapping,
- `operation_count_diff`,
- update propagation checks,
- tombstone delete/event handling,
- SCD2 current/history model checks when explicitly designed,
- ordering/window requirements for each advanced CDC mode,
- compiled artifact, state, result, and evidence visibility for supported and
  intentionally unsupported CDC behavior.

Required gate:

- resolve the advanced CDC modes and propagation checks gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: expand CDC propagation checks
```

## Post-MVP Milestone 28: future CLI commands and options

Build each command or option only after its underlying service semantics are
stable.

Goal:

- add CLI ergonomics without making command behavior a hidden product decision.

Build:

- `recon list`,
- `recon clean`,
- `recon debug`,
- `recon build`,
- documentation generation command,
- retry/resume commands,
- explicit `recon init` overwrite/force behavior,
- documented behavior for `--vars`, `--quiet`, and richer `--debug` output.

Required gate:

- resolve the future CLI commands and options gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` for the
  specific command or option being implemented,
- resolve the documentation generation command gate before adding docs
  generation behavior,
- resolve the `recon init` overwrite/force safety gate before adding any
  overwrite option.

Recommended commit message:

```text
feat: add recon list command
```

## Post-MVP Milestone 29: adapter test kit and adapter package split

Build this after the adapter API, typed check-plan payloads, capability
catalog, and local/dev adapter behavior are stable enough to externalize.

Goal:

- let adapter repositories evolve independently without drifting from core
  semantics.

Build:

- adapter compliance test kit,
- adapter compatibility matrix entries,
- adapter distribution strategy for separate adapter packages versus optional
  `recon-core[...]` extras,
- package split criteria,
- adapter migration/version guidance,
- first official adapter package preparation.

Required gate:

- resolve the adapter test kit and adapter package split gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`,
- resolve the profile-rendering and adapter diagnostic redaction conformance
  gate before publishing shared test-kit expectations or external adapter
  compatibility claims,
- resolve the diagnostic output message conformance gate before publishing
  shared adapter diagnostic assertions or adapter compatibility claims,
- include case-variant rendered-config redaction cases in shared adapter
  diagnostic assertions before creating or splitting the test-kit repository,
- include field-by-field adapter diagnostic redaction cases for diagnostic code,
  message, hint, path, `resource_type`, `resource_name`, `line`, `column`,
  `rendering.adapter_type`, and future structured diagnostic fields before
  creating or splitting the test-kit repository,
- include short numeric rendered-scalar cases, such as `port: 12`, `12.0`,
  `+12`, and `1.2e1`, across diagnostic codes, diagnostic text, resource metadata,
  `rendering.adapter_type`, and numeric `line`/`column` before creating or
  splitting the test-kit repository,
- include core render-sql compile-validation blocked-metadata integration cases
  before creating or splitting any test-kit harness that drives core compile
  flows,
- include malformed adapter factory result, malformed factory diagnostic
  payload, missing or invalid adapter API version declaration, and malformed
  capability support-state cases before creating or splitting the test-kit
  repository,
- include sanitized adapter factory exception and sanitized capability
  declaration exception cases before creating or splitting the test-kit
  repository or publishing external adapter compatibility claims,
- include adapter setup failure cases that assert no compiled SQL output,
  blocked compiled-check metadata, preserved diagnostics when factories return
  both adapters and diagnostics, de-duplicated repeated same-connection service
  diagnostics, and preserved distinct source/target connection diagnostics
  before creating or splitting the test-kit repository or publishing external
  adapter compatibility claims,
- resolve the adapter install extras and packaging strategy gate before
  publishing adapter packages or documenting adapter extras,
- resolve the DuckDB adapter repository extraction gate before moving the
  in-core DuckDB adapter into a `recon-duckdb` package or repository.

Recommended commit message:

```text
feat: add adapter compliance tests
```

## Post-MVP Milestone 30: semi-structured and JSON comparison

Build this after adapter metadata and typed operation payloads can represent
semi-structured projections safely.

Goal:

- compare JSON or semi-structured fields without hiding path semantics,
  type coercion, or adapter differences.

Build:

- JSON path syntax and validation,
- semi-structured projection typed operations,
- adapter capability and test-kit expectations,
- result and evidence visibility for projected values.

Required gate:

- resolve the semi-structured and JSON comparison gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add semi-structured comparisons
```

## Post-MVP Milestone 31: advanced evidence and reports

Build this after basic evidence, run results, failure details, and sensitive
data defaults are stable.

Goal:

- expand evidence without leaking data or overstating sampled/partial results.

Build:

- failure detail JSONL or streaming format for large mismatch sets,
- large-result pagination, row limits, and truncation semantics,
- masking and redaction policies,
- evidence templates,
- approval/sign-off artifacts,
- richer report levels,
- optional evidence vault integration boundaries.

Required gate:

- resolve the advanced evidence, redaction, templates, and sign-off gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`,
- resolve the failure detail JSONL and large result handling gate before adding
  non-CSV or streaming failure-detail formats.

Recommended commit message:

```text
feat: add advanced evidence outputs
```

## Post-MVP Milestone 32: Hub and external integrations

Build this only after package, adapter, artifact, and compatibility contracts
are stable enough for external automation.

Goal:

- connect Recon to ecosystem workflows without making integrations define core
  semantics.

Build:

- Recon Hub index metadata,
- GitHub Action,
- Airflow provider/operator,
- Dagster integration,
- dbt integration patterns,
- data catalog and issue/ticket integration boundaries.

Required gate:

- resolve the Hub and external integrations gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: define hub index metadata
```

## Post-MVP Milestone 33: source-location diagnostics

Build this after parser diagnostics and artifact diagnostic shapes can preserve
more precise source ranges.

Goal:

- report line, column, and range information without changing diagnostic
  artifacts casually.

Build:

- parser source range model,
- diagnostic line/column/range fields where supported,
- artifact compatibility review for diagnostic shape changes,
- tests for YAML, contract, and resource diagnostics.

Required gate:

- resolve the source-location diagnostics gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add source-location diagnostics
```

## Post-MVP Milestone 34: named identities and multi-grain contracts

Build this only after simple contract-level `grain.keys` and `cdc.keys`
behavior is stable and after a concrete advanced check-pack or CDC need exists.

Goal:

- support contracts that need multiple comparison or CDC identities without
  repeating raw key lists or guessing identity roles.

Build:

- authored `identities` YAML shape,
- identity role binding for checks and check packs,
- validation for unknown, wrong-kind, missing, or unsupported identity roles,
- compiled artifact, result, and evidence visibility for authored identity
  names and resolved keys.

Required gate:

- resolve the named identities and multi-grain contracts gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add named contract identities
```

## Post-MVP Milestone 35: public contract schema stabilization

Build this before any 1.0 release decision, even if it is scheduled before
some other post-MVP capability work.

Goal:

- stabilize the authored contract YAML schema as Recon Core's primary public
  API.

Build:

- contract schema versioning rules,
- machine-readable schema or equivalent validation reference,
- public compatibility promises for accepted contract syntax,
- migration policy for schema changes,
- compatibility docs and tests for schema-version behavior.

Required gate:

- resolve the public contract schema stabilization gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: stabilize public contract schema
```

## Post-MVP Milestone 36: deprecation and migration policy

Build this before 1.0 stabilization or before introducing any breaking public
contract change that needs migration guidance.

Goal:

- make public behavior changes predictable for users and automation.

Build:

- deprecation lifecycle policy,
- warning and diagnostic conventions for deprecated behavior,
- migration guide location and required content,
- changelog and compatibility-doc expectations,
- tests for deprecation warnings where behavior is implemented.

Required gate:

- resolve the deprecation and migration policy gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: define deprecation policy
```

## Post-MVP Milestone 37: remote and database state backend

Build this after local state, run lifecycle, connection/profile handling, and
adapter execution are stable.

Goal:

- support production recurring runs with shared state without hiding storage,
  locking, migration, or credential assumptions.

Build:

- remote or database-backed state backend interface,
- state table/schema versioning and migrations,
- locking and concurrency behavior,
- credential and profile handling,
- compatibility, result, and evidence references for remote state.

Required gate:

- resolve the remote and database state backend gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add database state backend
```

## Post-MVP Milestone 38: official package content releases

Build this only after package loading, compatibility ranges, and Hub metadata
are stable enough for supported packages.

Goal:

- publish official reusable check, policy, and evidence-template packages
  without making package contents hidden core behavior.

Build:

- first official package content scope,
- package resource schemas and compatibility ranges,
- package docs, examples, tests, and release process,
- support policy for official package versions.

Required gate:

- resolve the official package content release gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: define official package release scope
```

## Post-MVP Milestone 39: documentation site and examples repo split

Build this only when in-repo docs or examples become heavy enough that a repo
split improves maintenance.

Goal:

- split docs or large examples without breaking contributor workflow,
  compatibility examples, or release coordination.

Build:

- docs-site ownership and publish workflow,
- examples repo scope and CI expectations,
- cross-repo versioning and release coordination,
- contribution guidance for docs and examples.

Required gate:

- resolve the documentation site and examples repo split gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: plan docs and examples split
```

## Post-MVP Milestone 40: hosted service, UI, and enterprise controls

Build this only if product direction explicitly expands beyond the open-source
core framework.

Goal:

- keep cloud, UI, and enterprise policy work from redefining Recon Core's
  local-first framework contracts by accident.

Build:

- explicit product boundary for hosted or UI behavior,
- policy-control model and compatibility impact,
- security, privacy, tenancy, and evidence-storage boundaries,
- integration points that depend only on public CLI, artifact, adapter, package,
  or evidence contracts.

Required gate:

- resolve the hosted service, UI, and enterprise policy controls gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: define hosted product boundaries
```

## Post-MVP Milestone 41: domain-specific package boundaries

Build this only after generic package loading and official package release
rules are stable.

Goal:

- allow domain packages such as finance checks without turning core into a
  domain workflow, statistical matching, or MDM platform.

Build:

- domain-package acceptance criteria,
- package-owned versus core-owned semantics,
- compatibility, testing, and support expectations,
- explicit non-goal boundaries for fuzzy matching, automated repair,
  statistical reconciliation, and MDM-style behavior.

Required gate:

- resolve the domain-specific package boundaries gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
docs: define domain package boundaries
```

## Deferral list

Do not block MVP on:

- full Hub,
- package installer,
- `recon deps`,
- `recon debug`,
- `recon list`,
- `recon clean`,
- documentation generation command,
- `recon init` overwrite or force behavior,
- many adapters,
- hosted UI,
- persisted random sample,
- aggregate metric expansion beyond explicit `sum`,
- `recon_core.aggregate_equivalence`,
- schema policy checks,
- local custom check-pack resource execution beyond built-in packs,
- reusable local sampling, tolerance, and schema policy file resolution,
- macro reference validation,
- macro rendering or execution,
- package macro loading,
- endpoint resources and endpoint refs,
- executable query endpoints,
- selectors and partial execution,
- deep inheritance or templates,
- row-level value check execution beyond locked MVP scope,
- timestamp tolerance execution,
- row hash comparison,
- sampling modes beyond explicitly locked MVP behavior,
- multi-policy sampling composition,
- state, watermarks, persisted samples, and previous-failure state,
- artifact freshness and cache optimization,
- CDC execution and asymmetric delete representation,
- advanced CDC modes such as operation-column CDC, update propagation, operation
  count diff, tombstone CDC, and SCD2 CDC,
- future CLI commands and options beyond the MVP command set,
- package dependency installer and lock workflow,
- adapter package split and external adapter test kit,
- semi-structured and JSON comparison,
- advanced evidence workflows,
- result table writers,
- failure detail JSONL or streaming large-result handling,
- remote or database-backed state,
- named identities and multi-grain contracts,
- public contract schema freeze or 1.0 stabilization,
- deprecation and migration policy enforcement,
- official package content releases,
- adapter install extras and final adapter packaging strategy,
- documentation-site or examples-repo split,
- hosted service, UI, or enterprise policy controls,
- domain-specific package families,
- source-location diagnostic ranges,
- orchestration integrations.

## Design principle

Build the smallest complete loop first, then widen capability.
