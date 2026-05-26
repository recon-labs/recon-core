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
- duplicate resource-name validation for implemented resource kinds,
- manifest or internal parsed-project resource summaries where needed by
  Milestone 5 validation,
- macro file discovery and checksumming as source files only.

Do not build:

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
- duplicate resource names fail within resource kind and namespace,
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

- row-level checks require keys,
- CDC propagation checks require CDC keys,
- columns do not create checks,
- no silent all-column comparison,
- incompatible check/column type errors,
- sampling policy resolution,
- tolerance precedence.

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
  typed column declarations, all-column expansion, or row-level value checks
  still requires implementation of typed models, metadata validation, and
  artifact visibility,
- tolerance, null, and normalization resolution design is satisfied by
  `docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`;
  Milestone 5 should validate only the MVP policy surface and must not treat
  future timestamp, relative tolerance, reusable policy files, unrestricted
  regex features, custom SQL, or macros as executable behavior,
- do not validate references to local check packs, sampling policies, tolerance
  policies, schema policies, endpoint resources, or macros until those resource
  kinds are loaded through the shared ADR 0017 resource model.

Tests:

- each locked validation rule has passing and failing tests.
- future sampling, tolerance, column, check-pack config, and resource-reference
  validation expansions must reuse ADR 0016 phase ownership/code-family rules
  and lock their rule-specific diagnostics before implementation.

## Milestone 6: local/dev adapter

Build:

- base adapter interface,
- adapter API version declaration,
- local test adapter or DuckDB-style adapter,
- relation metadata,
- query execution,
- capability declarations,
- SQL rendering for typed plan operations,
- first internal adapter test-kit shape.

Required gates:

- resolve the profiles, connections, and secrets gate before adapter execution,
- resolve the adapter API, capability validation, and compiled SQL gate before
  implementing the adapter API or SQL rendering,
- resolve the typed operation catalog expansion gate before rendering or
  emitting additional typed operations,
- resolve the query endpoint support boundary gate if executable query
  endpoints are included.

Tests:

- metadata fetch,
- row count query,
- typed operation rendering,
- adapter API version compatibility,
- adapter capability validation.

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

- resolve the explicit authored checks and check registry gate before
  implementing explicit `checks: [...]` support or registry behavior that must
  serve explicit checks later,
- re-check the typed operation catalog expansion gate before executing any
  operation beyond the current compiled subset.

Tests:

- pass/fail cases,
- duplicate keys block row-level checks,
- null keys block row-level checks,
- aggregate metric result,
- check result serialization.

## Milestone 8: runner and results

Build:

- execution plan,
- run service,
- `target/run_results.json`,
- exit code mapping,
- terminal summary.

Tests:

- successful run,
- failing check run,
- runtime error,
- exit code mapping.

## Milestone 9: evidence

Build:

- failure detail writer,
- simple report writer,
- artifact references,
- sampling scope in evidence.

Tests:

- failure CSV written,
- report generated,
- row limit respected,
- artifact paths in run results.

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

## Post-MVP Milestone 16: package resource loading and package macros

Build this only after package/dependency behavior is designed and after local
resource loading is stable.

Goal:

- load package-provided resources through the same resource catalog as local
  resources,
- keep package namespaces explicit and compatibility ranges documented,
- allow package macro files only under the macro semantics already locked by
  Milestones 14 and 15.

Build:

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

- resolve the packages, deps, and package macro resources gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: load package resources
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

## Post-MVP Milestone 25: state, watermarks, and persisted samples

Build this after run lifecycle, result semantics, and local artifact storage
rules are stable.

Goal:

- make recurring validation reproducible through explicit state and safe
  watermark advancement.

Build:

- state backend shape,
- local state artifact format,
- watermark bootstrap and advancement rules,
- persisted sample-key records,
- previous-failure key records,
- compatibility/versioning rules for state formats.

Required gate:

- resolve the state, watermarks, and persisted samples gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add local reconciliation state
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
- retry/resume commands,
- documented behavior for `--vars`, `--quiet`, and richer `--debug` output.

Required gate:

- resolve the future CLI commands and options gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md` for the
  specific command or option being implemented.

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
- package split criteria,
- adapter migration/version guidance,
- first official adapter package preparation.

Required gate:

- resolve the adapter test kit and adapter package split gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

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

- masking and redaction policies,
- evidence templates,
- approval/sign-off artifacts,
- richer report levels,
- optional evidence vault integration boundaries.

Required gate:

- resolve the advanced evidence, redaction, templates, and sign-off gate in
  `.codex/brain_dumps/2026-05-20-milestone-design-prework-gates.md`.

Recommended commit message:

```text
feat: add evidence redaction policies
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

## Deferral list

Do not block MVP on:

- full Hub,
- package installer,
- `recon deps`,
- `recon debug`,
- `recon list`,
- `recon clean`,
- documentation generation command,
- many adapters,
- hosted UI,
- persisted random sample,
- aggregate metric expansion beyond explicit `sum`,
- `recon_core.aggregate_equivalence`,
- schema policy checks,
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
- state, watermarks, persisted samples, and previous-failure state,
- CDC execution and asymmetric delete representation,
- future CLI commands and options beyond the MVP command set,
- adapter package split and external adapter test kit,
- semi-structured and JSON comparison,
- advanced evidence workflows,
- source-location diagnostic ranges,
- SCD2 CDC,
- orchestration integrations.

## Design principle

Build the smallest complete loop first, then widen capability.
