# MVP Build Order

## Purpose

This document defines a practical implementation order for the first working Recon Core.

The goal is to avoid building too many advanced features before the core loop works.

## Milestone planning requirements

All MVP and post-MVP entries in this build-order document follow the general
milestone process in `docs/planning/milestone-process.md`. That process applies
to milestones, sub-milestones, roadmap items, and epics, and it is the source of
truth for lightweight prework, high-risk conformance matrices, and decimal
milestone splits.

This document defines sequence and capability homes. When a milestone is split
or superseded, update this build-order document alongside the roadmap, gates,
ADRs, compatibility docs, and tests so no orphan implementation plan remains.

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
  the applicable milestone design prework gate before
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
  the applicable milestone design prework gate.

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
- current DuckDB support renders SQL for existing typed plans and executes the
  relation-backed same-context row-count path,
- metadata fetches, broader check execution, run results, and evidence remain
  future milestones.

Required gates:

- resolve the profiles, connections, secrets, and adapter diagnostic redaction
  gate before adapter execution,
- resolve the adapter API, capability validation, and compiled SQL gate before
  implementing the adapter API or SQL rendering,
- keep the dimension-expanded adapter/profile conformance matrix in
  `docs/compatibility/adapter-api.md` current before future profile, adapter,
  diagnostic-redaction, or SQL-rendering changes,
- resolve the typed operation catalog expansion gate before rendering or
  emitting additional typed operations,
- keep Milestone 6 relation-only; resolve the query endpoint support boundary
  gate only if executable query endpoints are moved into scope,
- do not split `recon-duckdb` into an external package during Milestone 6.

Current pre-implementation alignment:

- `recon init` already writes the ADR 0020 selected profile/target shape with
  named `legacy` and `warehouse` connections in
  `connections/profiles.yml.example`.
- Adapter/profile rendering conformance rows are captured in
  `docs/compatibility/adapter-api.md#adapterprofile-rendering-conformance-matrix`
  and map required cases to existing tests or explicit future gates.

Tests:

- selected profile and target loading,
- selected target and referenced named-connection env var rendering,
- connection `type` values stay literal non-empty adapter types; templated
  `{{ ... }}`, `{% ... %}`, `{# ... #}`, or `env_var(...)` `type` values fail
  profile config before adapter resolution, do not invoke adapter
  factories/renderers, do not write compiled SQL, and do not leak the rendered
  environment value through diagnostics or artifacts,
- unsupported profile template syntax, including `{% ... %}` and `{# ... #}`,
  fails for referenced connections,
- secret redaction from diagnostics and artifacts,
- profile-backed adapter diagnostics, including adapter factory, adapter API
  compatibility, and render-phase diagnostics, do not leak rendered connection
  config keys or values,
- profile-backed adapter diagnostic codes suppress unsafe config keys and
  rendered profile values in delimiter-separated and separatorless forms,
  including examples such as `RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`,
  `RCsuper-secretLEAK`, and `RC12LEAK`,
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

## Milestone 7: check engine umbrella

Milestone 7 is split into implementation-bearing decimal sub-milestones. Do not
implement the umbrella milestone directly. Keep Milestone 8 as the owner of
runner/run-result artifact behavior and Milestone 9 as the owner of
evidence/report/failure-detail output unless a future split explicitly changes
those boundaries.

Split assignment:

- Milestone 7.1: check-engine boundary and result model,
- Milestone 7.2: adapter execution lifecycle and row count,
- Milestone 7.3: grain-key safety checks,
- Milestone 7.4: aggregate metric execution.

Each sub-milestone still needs its own current lightweight prework, Definition
of Done, dimension-expanded acceptance/conformance matrix rows, BDD workflow
scenarios, test plan, prompt/docs drift check, and phase exit review before
coding. Gates, tests, and blockers below are assigned to sub-milestones so no
implementation plan remains assigned only to this umbrella.

Out of scope for Milestone 7:

- `target/run_results.json`, terminal summary finalization, and exit-code/result
  artifact locking, which remain Milestone 8,
- failure details, reports, evidence artifacts, and evidence links, which remain
  Milestone 9,
- comparison placement, materialization, third-engine comparison, and any
  fallback strategy beyond the assigned adapter pushdown path, which must be
  resolved before the first executing sub-milestone that needs it,
- result/evidence sink writes, result tables, state writes, probabilistic
  summaries, Bloom/sketch key coverage, and large failure-detail stores, which
  remain assigned to later milestones below,
- query endpoint execution, which remains gated by a separate future query
  execution decision,
- CDC propagation check execution and `cdc.keys` runtime behavior, which remain
  a later CDC milestone,
- row-level value comparison, timestamp/string tolerance execution,
  normalization execution, and schema policy execution, which remain later
  milestones unless explicitly re-split.

### Milestone 7 Split Assignment Matrix

| Sub-milestone | Concrete implementation scope | Non-goals | High-risk surfaces touched | Required gates | Required ADRs or decisions | Required docs updates | Required acceptance/conformance matrix rows | Required BDD or workflow scenarios | Required tests | Public contract impact | Phase-exit review requirements | Blockers before coding |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Milestone 7.1 | Check-engine service boundary, check result model, status taxonomy, internal dispatch for already compiled check types, prerequisite/blocking representation, in-memory diagnostic/result serialization shape. | Adapter execution, profile-backed adapter lifecycle, `target/run_results.json`, evidence/report/failure-detail output, explicit authored `checks: [...]` support. | Check-engine boundary, result/status model, diagnostics, prerequisite/blocking semantics. | Diagnostic output message conformance gate; explicit authored checks and check registry gate if public registry behavior is introduced; generated artifact lifecycle remains out of scope. | ADR 0013 typed check-plan boundary; ADR 0014 key semantics and dependencies; result-model boundary that keeps generated run results in Milestone 8. | `docs/architecture/check-engine.md`, `docs/implementation/check-engine.md`, `docs/implementation/result-model.md`, `docs/implementation/errors-and-diagnostics.md`, `docs/compatibility/public-contract-inventory.md`, `docs/compatibility/compatibility-matrix.md`. | Check-engine boundary and result model; internal dispatch versus public check registry; public output and generated artifacts. | Compiled checks are loaded but adapter execution is still out of scope. | Result status serialization, reason-code serialization, prerequisite/blocking representation, diagnostic preservation, `not_executable` results for unsupported or not-yet-executable checks. | Planned check-engine/result public surface only; no stable generated result artifact or evidence schema. | Prove no adapter execution, source/target values, relation data, database errors, rendered profile values, run-result artifacts, evidence, reports, or failure details are emitted. | Current lightweight prework, Definition of Done, final 7.1 matrix rows, BDD scenario, test plan, prompt/docs drift check, and phase-exit checklist must be current. |
| Milestone 7.2 | Runtime compiled-contract loading, compiled-check to compiled-contract joining, runtime profile loading for referenced connections, adapter factory resolution and lifecycle for execution, same-context DuckDB relation-backed execution, row-count execution, sanitized adapter/runtime diagnostics. | Authored YAML parsing, recompilation, query endpoints, cross-adapter or cross-connection execution, key checks, aggregate execution, run-result artifacts, evidence, reports, failure details. | Adapter execution, profiles/secrets, diagnostics/redaction, SQL/rendered plan execution placement, source/target privacy, row-count result surface, runtime compiled-artifact loading. | Adapter/Profile Diagnostic Conformance Gate; source/target data privacy gate; comparison execution placement strategy gate for row count; renderer binding gate if renderer registries or shared helpers are introduced. | ADR 0013 typed check-plan boundary; ADR 0020 adapter/profile and SQL rendering boundary; comparison placement decision for row count. | `docs/compatibility/adapter-api.md`, `docs/architecture/adapter-interface.md`, `docs/implementation/adapter-interface-spec.md`, `docs/implementation/errors-and-diagnostics.md`, `docs/compatibility/public-contract-inventory.md`, `docs/compatibility/compatibility-matrix.md`. | Run boundary and compiled inputs; compiled-contract runtime loader; adapter execution lifecycle; adapter/profile diagnostic privacy; row-count execution; public output and generated artifacts. | A relation-backed DuckDB row-count check passes, fails, or errors. | Compiled-contract loader/join tests, row-count pass/fail/error, adapter lifecycle/setup failure, runtime diagnostic redaction, privacy assertions, negative tests for absent parser/compiler invocation and absent run/evidence artifacts. | Planned adapter execution and row-count public surface; no generated run-result or evidence schema. | Prove no authored YAML parsing or recompilation occurs, no raw rows are emitted, relation names/counts/errors follow privacy policy, no unsupported query/cross-adapter behavior appears, no run/evidence artifacts are written. | Adapter/profile diagnostic conformance, source/target privacy classification, row-count comparison placement, current prework, DoD, matrix rows, BDD scenario, test plan, and phase-exit checklist must be complete. |
| Milestone 7.3 | Grain-key null checks, duplicate-key checks, missing-key checks, extra-key checks, prerequisite/blocking semantics for dependent future row-level value checks, and bounded scan-budget policy for key-safety execution. | Row-level value comparison, inferred mappings, inferred grain keys, CDC key execution, sampling bypass of non-null or uniqueness requirements, raw key export, new contract YAML scan-budget settings, full user-facing scan-budget configuration, broad allow-unestimated production scan overrides. | Grain-key safety execution, key semantics, prerequisite/blocking results, source/target privacy, comparison placement, scan-budget and query-plan safety, sampling safety. | Comparison execution placement strategy gate for key checks; Gate 4L scan-budget and query-plan safety; source/target data privacy gate; key semantics gate; sampling safety rules. | ADR 0007 grain keys and row-level uniqueness; ADR 0014 key semantics and check dependencies; ADR 0013 typed check-plan boundary; ADR 0021 execution placement; ADR 0022 result/evidence privacy boundary. | `docs/planning/milestone-7-3-prework.md`, `docs/implementation/check-engine.md`, `docs/implementation/result-model.md`, `docs/implementation/errors-and-diagnostics.md`, `docs/compatibility/public-contract-inventory.md`, `docs/compatibility/compatibility-matrix.md`, key semantics docs if scope changes. | Grain-key null and duplicate checks; missing and extra key checks; dependent row-level check blocking; scan-budget allowed and fail-closed paths; future user-facing budget-settings boundary; public output and generated artifacts. | Null, duplicate, missing, or extra grain-key checks run before dependent row-level value checks; production unknown or over-budget scan preflight prevents execution instead of producing data-failure evidence. | Source/target null-key cases, duplicate fully non-null key cases, distinct fully non-null missing/extra key cases, empty-side cases, key type mismatch, blocked dependent row-level value checks, scan-budget allowed/fail-closed cases, no inferred grain or mapping behavior, no unbounded key movement, negative tests for absent run/evidence artifacts. | Planned grain-key safety and scan-budget non-execution public surface; no row-level value comparison, CDC execution, raw key export, contract-level scan-budget settings, general budget configuration, or evidence/failure-detail schema. | Prove sampling does not bypass key requirements, scan scope and budget status are explicit before execution, production unknown estimates and over-budget checks are `not_executable`, bounded local/dev fixture exceptions are explicit, no raw keys/row values are exported without a later privacy/evidence policy, dependent value checks remain future scope, and no evidence/failure artifacts are written. | Key-check comparison placement, Gate 4L scan-budget policy, privacy policy for key outputs, current prework, DoD, matrix rows, BDD scenario, test plan, and phase-exit checklist must be complete. |
| Milestone 7.4 | Current ungrouped `sum_diff` execution, current grouped aggregate diff execution, numeric tolerance for supported numeric aggregate comparisons, empty aggregate semantics, aggregate type-mismatch behavior. | Timestamp or string tolerance execution, null-equivalence or normalization execution, schema policy execution, new metric catalog expansion, run-result/evidence output. | Aggregate execution, typed operation execution, numeric tolerance behavior, source/target privacy, comparison placement. | Comparison execution placement strategy gate for aggregates; typed operation catalog expansion re-check before any operation beyond current compiled subset; source/target data privacy gate. | ADR 0013 typed check-plan boundary; ADR 0009 tolerance/null/normalization policy boundary for numeric tolerance; ADR 0020 adapter SQL rendering boundary. | `docs/compatibility/typed-check-plan.md`, `docs/framework/tolerance-policies.md` if tolerance behavior changes, `docs/implementation/check-engine.md`, `docs/implementation/result-model.md`, `docs/compatibility/public-contract-inventory.md`, `docs/compatibility/compatibility-matrix.md`. | Aggregate metric execution; public output and generated artifacts. | Ungrouped and grouped `sum` metric checks compare aggregates with numeric tolerance. | Ungrouped/grouped sum pass/fail/error, numeric tolerance, empty aggregate semantics, aggregate input/result type mismatch, negative tests for absent run/evidence artifacts. | Planned aggregate metric execution surface for current `sum` plans only; no new metric catalog, timestamp/string tolerance, normalization, schema policy, run-result, or evidence schema. | Prove aggregate outputs follow privacy policy, no new metric/tolerance/schema behavior appears, and run-result/evidence/report output remains Milestone 8/9 scope. | Aggregate comparison placement, typed operation catalog re-check, source/target privacy classification for aggregate values/grouped keys, current prework, DoD, matrix rows, BDD scenario, test plan, and phase-exit checklist must be complete. |

Cross-cutting gate assignments:

- Before Milestone 7.2 executes row-count checks, the implementation must lock
  the execution-placement decision for row counts and prove unsupported
  placement, third-engine comparison, materialization, and Python fallback paths
  fail clearly instead of silently changing strategy.
- Before Milestone 7.3 executes key checks, the implementation must lock the
  exact key-check placement strategy and the Gate 4L scan-budget policy. Key
  checks may execute only when scan scope and budget status are explicit.
  Production unknown, unavailable, unsupported, malformed, unsafe, or
  over-budget scan preflight outcomes are `not_executable`, not data failures.
  The bounded local/dev exception is allowed only when explicitly classified as
  local, relation-backed, and bounded. Milestone 7.3 must not add contract YAML
  scan-budget settings or broad user-facing budget configuration. If
  probabilistic, Bloom, or sketch-based key coverage is proposed, Gate 4K must
  be resolved first and exact versus probabilistic result semantics must be
  reflected in result/evidence wording.
- Before Milestone 7.4 executes aggregate checks, the implementation must lock
  the aggregate placement strategy and prove unsupported pushdown does not fall
  back to in-memory or cross-engine comparison without an explicit design.
- Production adapter compatibility claims for Milestone 7 execution behavior
  remain future adapter test-kit work. The shared conformance must prove native
  SQL optimization, dialect validation where useful, typed-operation rendering,
  and semantic behavior before external adapters claim warehouse-scale
  execution compatibility.
- Milestone 8 may record placement, capability, artifact, and sink-reference
  metadata in local run results, but it must not write evidence/report artifacts,
  result tables, state, or external sinks.
- Milestone 9 may write basic local evidence/report/failure-detail artifacts,
  but table-backed sinks, production result stores, state, and large external
  stores remain later milestones.

### Milestone 7.1: check-engine boundary and result model

Prework:

- `docs/planning/milestone-7-1-prework.md`

Build:

- check-engine service boundary behind `recon run`,
- check result model and status taxonomy,
- internal dispatch boundary for already compiled check types,
- prerequisite/blocking result representation,
- diagnostic/result serialization shape for in-memory results.

Non-goals:

- no adapter SQL execution,
- no profile-backed adapter lifecycle,
- no `target/run_results.json`,
- no failure detail or evidence artifact output,
- no explicit authored `checks: [...]` support.

Assigned gates and blockers:

- resolve the diagnostic output message conformance gate before check-engine
  diagnostics become user-facing output,
- resolve the explicit authored checks and check registry gate before adding
  public explicit authored check support or registry behavior that must serve it;
  this sub-milestone may define internal dispatch only if it does not expose
  unsupported authored checks,
- verify the result model does not pull Milestone 8 generated run-result
  artifacts into Milestone 7.1.

Required tests:

- check result status serialization,
- prerequisite/blocking result representation,
- check-engine diagnostics preserve code, severity, message, path, resource
  context, and hint where available,
- `not_executable` results for unsupported or not-yet-executable checks fail
  clearly instead of producing misleading evidence.

Phase exit review:

- no adapter execution is introduced,
- no source/target values, relation data, database errors, or rendered profile
  values are emitted,
- no generated run-result, evidence, report, or failure-detail artifacts are
  written.

### Milestone 7.2: adapter execution lifecycle and row count

Build:

- profile loading for execution using the existing selected profile/target and
  referenced-connection rules,
- runtime loading of matching compiled-contract artifacts and safe joins from
  compiled checks to compiled contract metadata,
- adapter factory resolution and lifecycle for run-time execution,
- same-context DuckDB relation-backed execution only,
- row count check execution,
- sanitized adapter/runtime diagnostics for row count execution.

Non-goals:

- no query endpoints,
- no authored YAML parsing or recompilation,
- no cross-adapter or cross-connection execution,
- no key-diff, null-key, duplicate-key, or aggregate execution,
- no failure-detail or evidence output.

Assigned gates and blockers:

- satisfy the Adapter/Profile Diagnostic Conformance Gate in
  `docs/compatibility/adapter-api.md` before loading rendered profiles or
  resolving adapters for execution,
- preserve literal adapter type routing: `type` must not be rendered from
  environment variables, and environment-specific adapter choices must use
  separate targets or named connections with literal `type` values; resolved
  adapter `adapter_type` metadata must match the literal profile `type` before
  execution,
- if this sub-milestone introduces a renderer registry, execution-time renderer
  selection, or any public/shared rendering helper that accepts an explicit
  renderer, validate the renderer's declared `adapter_type` against the
  resolved adapter type before rendering,
- require adapter/profile diagnostic redaction conformance to cover unsafe
  rendered profile keys or values independently in diagnostic code, message,
  hint, path, `resource_type`, `resource_name`, `line`, `column`, and future
  structured diagnostic fields, including unsafe config key diagnostic-code
  variants such as `RC_PASSWORD_LEAK` and `RCPASSWORDLEAK`, short numeric
  rendered scalars such as port values, separatorless value embeddings such as
  `RC12LEAK`, and equivalent formatted variants such as `12.0`, `+12`, and
  `1.2e1`, while preserving safe adapter diagnostic codes such as
  `RC_ADAPTER_CAPABILITY_UNSUPPORTED`,
- preserve the existing adapter-aware compile contract while adding run-time
  adapter setup behavior: compile setup failures continue to write no SQL and
  mark affected compiled checks blocked, while run-time setup failures preserve
  factory diagnostics even when an adapter is also returned, de-duplicate
  repeated same-connection setup diagnostics, and keep distinct source/target
  connection setup diagnostics visible,
- resolve the source/target data privacy, evidence, and failure-detail policy
  gate before row count execution can emit relation names, runtime adapter
  errors, database errors, row counts, or data-derived values through terminal
  output, diagnostics, logs, run results, evidence, or adapter test-kit
  snapshots,
- resolve the comparison execution placement strategy gate for row count
  execution before executing typed plans.

Required tests:

- row count pass/fail/error cases,
- missing, malformed, unsafe, incompatible, or mismatched compiled-contract
  artifacts,
- compiled-check to compiled-contract joins without parser/compiler invocation,
- adapter lifecycle and setup failure cases,
- adapter/profile diagnostics preserve safe actionable messages and suppress
  rendered profile values,
- row count public output follows source/target privacy defaults.

Phase exit review:

- row count execution emits no raw source/target rows,
- runtime compiled-contract loading does not expose raw artifact contents and
  does not reparse authored YAML or recompile contracts,
- relation names, row counts, adapter errors, and database errors follow the
  resolved source/target privacy policy,
- no `target/run_results.json`, evidence, report, or failure-detail artifacts are
  written.

### Milestone 7.3: grain-key safety checks

Build:

- null source/target key checks,
- duplicate source/target key checks,
- missing key checks,
- extra key checks,
- prerequisite/blocking semantics for dependent future row-level value checks,
- bounded scan-budget preflight for key-safety execution before source/target
  scans.

Non-goals:

- no row-level value comparison,
- no automatic source-target mapping guesses,
- no inferred grain keys,
- no CDC key execution,
- no sampling bypass of non-null or uniqueness requirements,
- no raw key export,
- no contract YAML scan-budget settings,
- no full user-facing scan-budget configuration,
- no broad allow-unestimated production scan overrides.

Assigned gates and blockers:

- resolve the comparison execution placement strategy gate for key checks before
  executing typed plans,
- resolve Gate 4L scan-budget and query-plan safety before executing key checks;
  key checks may execute only when scan scope and budget status are explicit,
- treat production unknown, unavailable, unsupported, malformed, unsafe, or
  over-budget scan preflight outcomes as `not_executable`, not data failures,
- allow bounded local/dev scan-budget exceptions only when explicitly classified
  as local, relation-backed, and bounded,
- preserve locked key semantics: `grain.keys` means comparison identity,
  `cdc.keys` means CDC/change propagation identity, row-level checks require
  `grain.keys`, and row-level value and row-matching checks require non-null and
  unique source and target grain keys,
- preserve the source/target data privacy, evidence, and failure-detail policy
  gate before key checks emit comparison keys, failure examples, runtime adapter
  errors, database errors, or data-derived values through terminal output,
  diagnostics, logs, run results, evidence, or adapter test-kit snapshots,
- verify sampling does not remove non-null or uniqueness requirements.

Required tests:

- null source/target key cases,
- duplicate source/target key cases,
- missing key and extra key cases,
- scan-budget allowed and fail-closed cases,
- production unknown, unavailable, unsupported, malformed, unsafe, and
  over-budget scan preflight cases return `not_executable`,
- bounded local/dev fixture exceptions are explicit,
- null or duplicate keys block dependent row-level value checks,
- no inferred grain or source-target mapping behavior.

Phase exit review:

- no raw key examples or row-level values are exported unless a later privacy and
  evidence policy explicitly allows that surface,
- scan scope and budget status are explicit before execution,
- production unknown or over-budget scan preflight outcomes are
  `not_executable`, not data failures,
- bounded local/dev scan-budget exceptions are explicit and bounded,
- no contract YAML scan-budget settings or broad user-facing budget
  configuration are introduced,
- dependent row-level value checks remain future scope,
- no evidence/report/failure-detail artifacts are written.

### Milestone 7.4: aggregate metric execution

Build:

- current ungrouped `sum_diff` execution,
- current grouped aggregate diff execution,
- numeric tolerance application for supported numeric aggregate comparisons,
- empty aggregate semantics,
- aggregate type mismatch behavior.

Non-goals:

- no timestamp or string tolerance execution,
- no null-equivalence or normalization execution for row-level values,
- no schema policy execution,
- no new metric catalog expansion beyond current compiled `sum` plans.

Assigned gates and blockers:

- resolve the comparison execution placement strategy gate for aggregate checks
  before executing typed plans,
- re-check the typed operation catalog expansion gate before executing any
  operation beyond the current compiled subset,
- preserve the source/target data privacy, evidence, and failure-detail policy
  gate before aggregate checks emit aggregate values, grouped keys, relation
  names, runtime adapter errors, database errors, or data-derived values through
  terminal output, diagnostics, logs, run results, evidence, or adapter test-kit
  snapshots.

Required tests:

- ungrouped sum diff pass/fail/error cases,
- grouped aggregate diff pass/fail/error cases,
- numeric tolerance behavior for current `sum` metrics,
- empty aggregate result semantics,
- aggregate input/result type mismatch behavior.

Phase exit review:

- aggregate results follow the source/target privacy policy,
- no timestamp/string tolerance, normalization, schema policy, or new metric
  operation behavior is introduced,
- run-result artifacts and evidence/report output remain Milestone 8 and
  Milestone 9 scope.

## Milestone 8: runner and results

Build:

- execution plan,
- run service,
- first user-facing scan-budget settings decision for `recon run` execution
  policy,
- `target/run_results.json`,
- local run-result artifact metadata for execution placement, adapter/capability
  status, scan scope, budget status, artifact references, and future
  sink-reference placeholders,
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
- resolve Gate 4L before introducing the first user-facing scan-budget settings
  surface for `recon run`. Milestone 8 owns the first decision for where scan
  limits or opt-ins live across project config, profile/target policy,
  run-policy config, command options, or future contract policy. Contract YAML
  scan-budget settings stay out of scope unless a separate public schema
  decision explicitly admits them.
- resolve the result/evidence sink metadata boundary before adding sink status or
  sink references to run results. Milestone 8 may record local metadata only; it
  must not write table sinks, evidence sinks, state, or external stores.
- resolve the selector-readiness portion of the selectors and contract
  selection semantics gate before finalizing run-result scope metadata. Milestone
  8 must not implement `--select`, `--exclude`, `selectors.yml`, partial run, or
  partial compile, but run results should not assume every future run is
  whole-project forever.

Tests:

- successful run,
- failing check run,
- runtime error,
- exit code mapping,
- run results and terminal output preserve diagnostic code and message for
  runtime, adapter, prerequisite, and result-write failures,
- run results and terminal output follow source/target data privacy defaults for
  raw rows, keys, values, aggregates, relation names, query text, and runtime
  error text,
- local run-result artifacts include stable metadata for placement/capability
  decisions and scan-budget decisions without implying evidence, sink, state,
  or result-table writes,
- first scan-budget settings tests cover the selected settings home, unknown
  estimate behavior, over-budget behavior, explicit opt-ins if admitted, and
  Recon-computed budget status rather than user-provided final status,
- run-result scope metadata can represent whole-project runs now and can evolve
  to selected-scope runs later without changing the meaning of existing fields.

## Milestone 9: evidence

Build:

- failure detail writer,
- simple report writer,
- artifact references,
- local-only artifact modes and optional local-output behavior,
- bounded/truncated failure-detail policy,
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
- resolve the result/evidence sink boundary before evidence links can reference
  table-backed sinks or external stores. Milestone 9 local artifacts must not
  silently become required when a future sink-only mode is configured.
- resolve the selector-readiness portion of the selectors and contract
  selection semantics gate before finalizing evidence scope wording. Milestone 9
  must not implement selectors, but evidence should clearly identify whole-run
  scope and avoid wording that would make future selected-scope evidence
  misleading.

Tests:

- failure CSV written,
- report generated,
- row limit respected,
- artifact paths in run results,
- evidence and report diagnostics preserve safe actionable messages instead of
  emitting only diagnostic codes or hints,
- failure details, reports, and evidence follow source/target data privacy
  defaults for raw-value export, masking/redaction, truncation, and generated
  artifact references,
- disabled local evidence, local-only evidence, terminal-only output, and future
  sink-only configuration cases fail or report clearly according to the locked
  evidence mode instead of silently writing unexpected files,
- evidence scope wording can represent whole-project runs now and can evolve to
  selected-scope runs later without implying unselected contracts or checks were
  reconciled.

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

Future gate priority order:

1. Gate 5G with Post-MVP Milestone 10.7 for the user-facing agent onboarding
   pack and installer.
2. Gate 4L before future execution phases grow beyond row count.
3. Gate 3L and Gate 3M with Post-MVP Milestone 12.5 for discovery, profiling,
   suggestion, relation scope, and candidate lifecycle behavior.
4. Gate 4M before selectors, sampling, state, CDC, or filters affect execution
   scope.
5. Gate 4N with Post-MVP Milestone 25.6 after state/history exists.
6. Gate 6E with Post-MVP Milestone 25.7 after result, evidence, and history
   foundations exist.
7. Gate 6F with Post-MVP Milestone 32.1 after artifact metadata is stable.
8. Gate 5H with Post-MVP Milestone 32.2 after CLI and Python command surfaces
   are stable.
9. Gate 6D with Post-MVP Milestone 32.5 after evidence, result, and
   integration boundaries exist.
10. Gate 9A with Post-MVP Milestone 42, then Gate 9 with Post-MVP Milestone
    42.5, as optional non-default AI and semantic package work.

Future gate-to-milestone mapping summary:

| Gate | Primary milestone | Also applies to |
| --- | --- | --- |
| Gate 3L | Post-MVP Milestone 12.5 | Any discovery/profile/suggest, metadata, profiling, or relation-scope feature |
| Gate 3M | Post-MVP Milestone 12.5 | Post-MVP Milestones 25.6, 42, 42.5, and any generated tests |
| Gate 3A amendment | Post-MVP Milestone 11 | Post-MVP Milestone 12.5 and Milestone 7.4 aggregate suggestion/execution boundaries |
| Gate 4L | Cross-cutting | Milestones 7.3, 7.4, 8, 9, Post-MVP Milestones 10.6, 12.5, 18, 21, 24, 25, 25.5, 29, and 31 |
| Gate 4M | Post-MVP Milestones 24/25/26 area | Post-MVP Milestones 10.6, 24, 25, 26, 27, and 27.5 |
| Gate 4N | Post-MVP Milestone 25.6 | Post-MVP Milestone 25.7, Post-MVP Milestone 31, and any adaptive threshold or drift feature |
| Gate 5G | Post-MVP Milestone 10.7 | Post-MVP Milestones 12.5, 32.2, 32.5, 42, and 42.5 |
| Gate 5H | Post-MVP Milestone 32.2 | Post-MVP Milestones 32.5, 42, and 42.5 |
| Gate 6D | Post-MVP Milestone 32.5 | Post-MVP Milestones 25.6, 25.7, 32.2, and 42.5 |
| Gate 6E | Post-MVP Milestone 25.7 | Post-MVP Milestone 32.1, Post-MVP Milestone 32.5, and future hosted dashboards |
| Gate 6F | Post-MVP Milestone 32.1 | Post-MVP Milestone 32, Post-MVP Milestone 32.2, Post-MVP Milestone 25.7, and external event sinks |
| Gate 9 | Post-MVP Milestone 42.5 | Post-MVP Milestones 12.5, 32.2, 32.5, and 42 |
| Gate 9A | Post-MVP Milestone 42 | Post-MVP Milestone 42.5, Post-MVP Milestone 31, and Post-MVP Milestone 29 semantic package conformance |

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
- selected-scope artifact freshness rules that future selector-scoped compile,
  SQL rendering, run result, and evidence outputs can reuse,
- cache/invalidation keys based on authored files, project config, relevant
  resource checksums, command options, and adapter-capability inputs,
- stale-artifact diagnostics and safe fallback behavior,
- optional skip-unchanged behavior that is visible in terminal output and
  machine-readable artifacts,
- compatibility rules for any freshness metadata added to generated artifacts.

Required gate:

- resolve the generated artifact lifecycle and cleanup gate in
  the applicable milestone design prework gate,
- resolve the artifact freshness and cache optimization gate in
  the applicable milestone design prework gate.

Recommended commit message:

```text
feat: add artifact freshness checks
```

## Post-MVP Milestone 10.6: minimal contract and path selectors

Build this after Post-MVP Milestone 10.5 defines artifact freshness and scoped
generated-output rules.

Goal:

- support a small, explicit selector subset early without waiting for the full
  selector system.

Build:

- `recon compile --select "contract:..."`,
- `recon compile --render-sql --select "contract:..."`,
- `recon run --select "contract:..."`,
- `recon run --exclude "contract:experimental_*"` only if the selector gate
  locks contract-pattern syntax and select/exclude precedence for the minimal
  selector subset,
- `path:...` selection for contract files if path matching can be defined
  against project-relative manifest paths without file-scanning ambiguity,
- exact file-path selection before directory-prefix selection,
- multi-contract file selection that includes every contract in the selected
  file unless narrower composition is explicitly designed,
- contract/path selectors include metric-generated checks for selected
  contracts; individual metric/check selection remains later `check:...` scope,
- contract exclusion by exact name, and by simple contract-name pattern only if
  that pattern syntax is explicitly admitted into the minimal selector gate,
- selected-scope metadata in compiled artifacts, rendered SQL metadata, run
  results, terminal summaries, and evidence references touched by the selected
  invocation,
- diagnostics for invalid selector syntax, unknown selector method, selectors
  that match nothing, and selectors that match resources outside the command's
  supported scope.

Non-goals:

- `selectors.yml`,
- named `selector:...` references,
- check-level `check:...` selection,
- tag/domain/team/package selectors,
- state/result selectors,
- graph operators, dependency expansion, or transformation-style selection,
- partial parse or partial manifest generation.

Required gate:

- resolve the selectors and contract selection semantics gate in
  the applicable milestone design prework gate,
- resolve the windowed and incremental reconciliation semantics gate before
  selector scope can act as execution-window, event-time, processing-time,
  watermark, partition, or backfill scope,
- confirm Post-MVP Milestone 10.5 artifact freshness and cleanup behavior is
  sufficient for selector-scoped generated artifacts.

Recommended commit message:

```text
feat: add minimal contract selectors
```

## Post-MVP Milestone 10.7: user-facing agent onboarding pack and installer

Build this after the MVP release-readiness decision and after the core docs can
describe the supported local project workflow accurately.

Goal:

- provide canonical Recon agent instructions for users' own data and warehouse
  projects without duplicating rules across agent-specific wrappers.

Build:

- one canonical user-facing agent instruction pack,
- generated wrappers for supported agent targets from that canonical source,
- `recon agent init --target generic`,
- tool-specific `recon agent init --target ...` modes after each wrapper is
  designed,
- `recon agent init --target all`,
- later target support only after its wrapper and update behavior are designed,
- safe write locations such as `AGENTS.md`, `llms.txt`, `.recon/agent/...`,
  optional tool-specific wrapper folders, and later local tool config files,
- update, doctor, stale-version, merge, skip, and overwrite behavior,
- tests proving generated files do not contain secrets and wrappers point back
  to the canonical `.recon/agent` content.

Do not build:

- a local MCP server,
- AI assistant behavior,
- automated contract mutation,
- expensive scans or evidence publication through agent instructions.

Required gate:

- resolve Gate 5G: User-Facing Agent Skill And Prompt-Pack Safety in the
  applicable milestone design prework gate before implementation.

Recommended commit message:

```text
feat: add user-facing agent onboarding
```

## Post-MVP Milestone 11: aggregate metrics expansion

Build this after Milestones 1-10 are complete and after the 0.1
release-readiness decision. It also depends on Milestone 7.4's current
aggregate metric execution boundary.

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
- check-engine execution for the new aggregate metric checks, extending the
  Milestone 7.4 aggregate execution boundary,
- result and evidence fields for aggregate metric comparisons.

Tests:

- each supported metric type compiles into the expected typed plan,
- unsupported metric types produce diagnostics,
- grouped and ungrouped aggregate behavior is covered separately,
- adapter capability validation blocks unsupported aggregate operations,
- run results and evidence preserve metric names and aggregate details.

Required gate:

- resolve the aggregate metrics expansion gate in
  the applicable milestone design prework gate before
  implementation,
- preserve the Gate 3A suggestion boundary: suggestion support does not imply
  execution support. Future discovery/profile/suggest work may draft aggregate
  candidates, but aggregate metrics beyond the currently supported execution
  surface remain advisory until this milestone locks typed plans, adapter
  capabilities, results, evidence, and tests.

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
  the applicable milestone design prework gate before
  implementation.

Recommended commit message:

```text
feat: add schema policy checks
```

## Post-MVP Milestone 12.5: metadata discovery, data profiling, contract suggestions, and relation scope selection

Build this after adapter metadata access is designed and after the project can
represent safe multi-relation output without confusing suggestions for accepted
contracts.

Goal:

- provide scoped metadata discovery, row-data profiling, and advisory contract
  suggestions without turning inferred facts into accepted Recon behavior.

Build:

- `recon discover` for metadata/catalog inspection,
- `recon profile` for scoped row-data statistics,
- `recon suggest` for advisory candidate generation from discovery, profile,
  and later history,
- relation identifier handling for schema/table, database/schema/table, adapter
  naming, quoting, and case sensitivity,
- explicit scope flags such as `--schema`, repeatable `--table`, repeatable
  `--exclude-table`, and later relation-type flags,
- include/exclude precedence,
- stable multi-relation artifact layout,
- per-relation diagnostics and partial-failure behavior,
- provenance for discovered or suggested facts,
- candidate metadata that distinguishes catalog-derived, profile-derived,
  history-derived, lineage-derived, rule-template-derived, model-assisted, and
  human-authored suggestions,
- confidence, risk, review, duplicate, low-value, and evaluation metadata for
  generated candidate checks.

Do not build:

- accepted contract behavior from suggestions,
- automatic grain, tolerance, mapping, filter, policy, or business-rule
  enforcement,
- unbounded row-data scans for schema-level profiling or suggestion,
- aggregate execution for suggestions that current execution milestones do not
  support.

Required gates:

- resolve Gate 3L: Metadata Discovery, Profiling, Contract Suggestion, And
  Relation Scope Safety,
- resolve Gate 3M: Automated Test Candidate Lifecycle And Evaluation,
- resolve Gate 4L: Execution Cost, Scan Budget, And Query Plan Safety for
  row-data scans,
- preserve the Gate 3A aggregate suggestion boundary for unsupported aggregate
  metrics,
- resolve Gate 9: AI Assistant Provider, Prompt, And Model Governance before
  any model-assisted or LLM-assisted suggestions are included,
- apply source/target privacy rules before profile or suggestion output can
  expose sampled values, identifiers, or data-derived statistics.

Recommended commit message:

```text
feat: add metadata discovery and suggestions
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
  the applicable milestone design prework gate before
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
- macro dispatch as the primary comparison engine,
- arbitrary custom SQL behavior hidden behind macro names.

Required gate:

- resolve the macro reference semantics gate in
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.
- resolve the generated artifact lifecycle and cleanup gate if query endpoint
  execution writes query-specific compiled SQL, results, evidence, or debug
  artifacts.

Recommended commit message:

```text
feat: execute query endpoints
```

## Post-MVP Milestone 19: rich selectors and subset execution expansion

Build this after minimal contract/path selectors prove the selected-scope
metadata, artifact freshness, and run/evidence behavior.

Goal:

- expand selector support without producing misleading partial artifacts or
  evidence.

Build:

- `selectors.yml` and named `selector:...` schema,
- `recon run --select "selector:critical_reconciliations"`,
- check-level `check:...` selection semantics,
- `recon run --select "check:customer_revenue.row_count"`,
- richer `--select` and `--exclude` composition,
- contract-pattern exclusion not admitted into the minimal selector subset,
- optional tag/domain/team/package selectors only after selector metadata is
  explicit and documented,
- state/result selectors only after state and run-result artifacts can support
  them safely,
- selected-scope metadata in artifacts and run results,
- diagnostics for empty or invalid selections.

Required gate:

- resolve the selectors and contract selection semantics gate in
  the applicable milestone design prework gate.
- resolve the generated artifact lifecycle and cleanup gate before selector
  compile/run writes partial or scoped generated artifacts.

Recommended commit message:

```text
feat: add rich selectors
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
  the applicable milestone design prework gate.

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
- `requires_non_null_grain` and `requires_unique_grain` metadata for row-level
  value checks,
- prerequisites on `null_source_keys`, `null_target_keys`,
  `duplicate_source_keys`, and `duplicate_target_keys`,
- prerequisite blocking with `blocked_by` and machine-readable reason codes for
  null/duplicate keys,
- resolved column and policy payloads in typed plans,
- result, failure-detail, and evidence output for value mismatches.

Required gate:

- resolve the row-level value check execution gate in
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
- probabilistic or sketch-based sampled key coverage only if Gate 4K is resolved
  and exact versus probabilistic semantics are explicit,
- future mode diagnostics for random, previous-failure, stratified, and
  high-value samples until their state requirements are implemented.

Required gate:

- resolve the sampling execution modes gate in
  the applicable milestone design prework gate,
- resolve Gate 4L before sampling modes scan source/target data broadly,
- resolve Gate 4M before sampling modes define partition, window, event-time,
  processing-time, or incremental scope,
- resolve the probabilistic key-diff/Bloom/sketch gate before using compact
  summaries for sampled key coverage, including false-positive safeguards,
  canonical composite-key serialization, partition/window scope, multi-phase
  lifecycle, intermediate summary storage, and exact-confirmation rules.

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
  the applicable milestone design prework gate.

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
- result tables or evidence sinks; those remain result/evidence store surfaces,
  not state by default.

Required gate:

- resolve the state, watermarks, and persisted samples gate in
  the applicable milestone design prework gate,
- resolve Gate 4M before watermark, incremental-window, replay, backfill, or
  state-derived filters affect check scope,
- resolve Gate 4L before stateful execution can run broad source/target scans,
- prove watermark advancement, persisted sample keys, and previous-failure state
  are explicit, versioned, and recoverable without relying on result tables or
  evidence sinks.

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
- explicit destination selection for source, target, or third configured
  connection when adapter capabilities allow it,
- table schema/versioning and migration rules,
- write modes, retention, idempotency, and retry behavior,
- sink requiredness and sink-write status semantics,
- adapter/profile requirements and credential-safe diagnostics,
- links between result tables, `run_results.json`, evidence artifacts, failure
  details, and state records,
- privacy rules for sensitive values written to tables.

Required gate:

- resolve the result table writer gate in
  the applicable milestone design prework gate,
- resolve Gate 4L before production result-table work records or depends on
  scan-cost metadata from execution paths,
- resolve adapter write/sink capability requirements before writing through any
  source, target, or third configured connection,
- define behavior for unsupported sink capability, unsafe destination config,
  schema migration failure, partial writes, retries, idempotency conflicts,
  retention, and required sink failures before implementation.

Recommended commit message:

```text
feat: add production result tables
```

## Post-MVP Milestone 25.6: historical profiles, drift, and statistical baseline checks

Build this after local state, run lifecycle, historical metric storage, and
result/evidence semantics are stable enough to explain what history was used.

Goal:

- support explicit baseline and drift checks without silently mutating accepted
  static tolerances.

Build:

- historical profile and metric records,
- baseline artifact shape and versioning,
- minimum history and training-window rules,
- holdout or evaluation-window rules where supported,
- first explicit baseline/anomaly check model,
- anomaly feedback states,
- retention and privacy policy for historical metrics,
- result and evidence wording that distinguishes fixed thresholds from learned
  baselines.

Do not build:

- `tolerance: auto` as a silent mutation of accepted contract behavior,
- hidden adaptive thresholds,
- scorecards or action/remediation workflows.

Required gates:

- resolve Gate 4N: Statistical Baseline, Drift, And Adaptive Threshold Safety,
- resolve Gate 3M if baseline or anomaly candidate checks are generated,
- apply Gate 6 source/target privacy before storing or publishing historical
  metrics,
- resolve Gate 6D before baseline feedback triggers any action.

Recommended commit message:

```text
feat: add baseline drift checks
```

## Post-MVP Milestone 25.7: quality rollups, ownership, and SLA scorecards

Build this after run results, evidence, history, and score input semantics are
stable.

Goal:

- summarize quality health without hiding skipped checks, errors, partial runs,
  sampled scope, unsupported checks, stale results, missing evidence, or
  ownership gaps.

Build:

- score dimensions for pass/fail/error, freshness, volume, completeness,
  uniqueness, consistency, SLA adherence, evidence availability, and coverage,
- score unavailable and incomplete states,
- owner/team metadata and privacy classification,
- rollups at check, contract, dataset/relation, domain/team, and project level,
- links from score output back to detailed run results and evidence,
- trend windows after historical metrics are available.

Do not build:

- a single score that replaces detailed evidence,
- action triggers without the remediation/action safety gate,
- hosted dashboard behavior.

Required gates:

- resolve Gate 6E: Quality Rollup, Ownership, And SLA Scorecard Semantics,
- resolve Gate 4N when scorecards use baselines or historical metrics,
- resolve Gate 6D before scorecards can trigger webhooks, tickets,
  notifications, remediation, contract edits, or threshold updates.

Recommended commit message:

```text
feat: add quality scorecards
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
- probabilistic or sketch-based CDC key coverage only if Gate 4K is resolved,
- explicit `cdc.keys` validation,
- resolved CDC identity artifact shape, if CDC checks need resolved identity
  fields instead of the current authored CDC policy snapshot,
- CDC result and evidence fields.

Required gate:

- resolve the CDC first implementation scope gate in
  the applicable milestone design prework gate,
- resolve Gate 4M before CDC windows, watermarks, backfills, or incremental
  filters affect reconciliation scope,
- resolve the probabilistic key-diff/Bloom/sketch gate before using compact
  summaries for CDC coverage, including bidirectional probing, partition/window
  scope, false-positive handling, exact-confirmation behavior, and evidence
  wording for suspected missing or extra records.

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
  the applicable milestone design prework gate,
- resolve Gate 4M if delete behavior depends on event-time, processing-time,
  backfill, or watermark windows.

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
  the applicable milestone design prework gate,
- resolve Gate 4M for every incremental, event-time, processing-time, watermark,
  backfill, replay, or partition-window propagation mode.

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
- `recon debug profile` for selected profile, target, environment-variable,
  and connection-config shape diagnostics that do not open adapter connections,
- `recon debug connection` for adapter resolution, dependency availability,
  connection, metadata, and capability diagnostics with sanitized adapter and
  database failure text,
- `recon debug contract` for compiled contract/check linkage, relation endpoint
  readiness, placement eligibility, and adapter capability eligibility before
  execution,
- `recon debug run --check ...` for safe structured context around one failed
  run/check after the result model can identify selected run scope,
- an explicitly opted-in local secure debug artifact for richer diagnostics
  after artifact lifecycle, path safety, retention, cleanup, and redaction
  rules are locked,
- `recon build`,
- documentation generation command,
- retry/resume commands,
- explicit `recon init` overwrite/force behavior,
- documented behavior for `--vars`, `--quiet`, and richer `--debug` output.

Deferred from this milestone:

- public terminal/log output that prints raw SQL, rendered SQL, raw database
  engine error text, tracebacks, credentials, DSN fragments, rendered profile
  values, source/target query text, or raw row/value data,
- opt-in native database error and rendered SQL disclosure, which belongs with
  the advanced secure debug/evidence artifact work in Post-MVP Milestone 31
  unless a later gate explicitly moves it earlier,
- adapter test-kit debug snapshots, which belong with Post-MVP Milestone 29.

Required gate:

- resolve the future CLI commands and options gate in
  the applicable milestone design prework gate for the
  specific command or option being implemented,
- resolve the debug commands and secure debug artifacts gate before adding any
  `recon debug ...` command, richer `--debug` behavior, secure debug artifact,
  native-error disclosure, rendered-SQL disclosure, or debug snapshot,
- resolve diagnostic output message conformance before any debug command prints
  diagnostics,
- resolve adapter/profile diagnostic conformance before profile-backed adapter
  resolution, connection checks, adapter metadata reads, adapter capability
  reads, adapter query attempts, or adapter test-kit debug snapshots,
- resolve source/target privacy before any debug command, log, artifact,
  snapshot, or result view can expose source/target identifiers, query text,
  relation names, counts, keys, values, database errors, or failure details,
- resolve generated artifact lifecycle and cleanup before writing a local secure
  debug artifact,
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
- adapter write/sink conformance for result and evidence sink capabilities,
- probabilistic summary capability conformance for Bloom/sketch-like operations,
- native SQL optimization and dialect validation conformance for production
  warehouse adapters,
- first official adapter package preparation.

Required gate:

- resolve the adapter test kit and adapter package split gate in
  the applicable milestone design prework gate,
- satisfy the Adapter/Profile Diagnostic Conformance Gate in
  `docs/compatibility/adapter-api.md` before creating or splitting the shared
  test-kit repository, publishing shared test-kit expectations, splitting
  `recon-duckdb`, publishing production adapter packages, or making external
  adapter compatibility claims,
- satisfy the Renderer Output And Artifact Publication Conformance Gate in
  `docs/compatibility/adapter-api.md` before creating or splitting the shared
  test-kit repository, publishing shared renderer expectations, splitting
  `recon-duckdb`, introducing renderer registries, publishing production
  adapter packages, or making external adapter compatibility claims,
- include profile env-var rendering conformance before creating or splitting
  the test-kit repository: `{{ env_var(...) }}` and bare `env_var(...)` forms
  in non-routing fields, defaults, missing variables, unsupported bare
  expressions, embedded env-var calls, filters, and unsupported Jinja
  statement/comment fragments such as `{% ... %}` and `{# ... #}` must either
  render safely or fail before adapter resolution instead of surviving as
  literal config,
- include literal adapter `type` conformance before creating or splitting the
  test-kit repository: templated `{{ ... }}`, `{% ... %}`, `{# ... #}`, or
  `env_var(...)` `type` values must fail before adapter resolution, must not
  invoke adapter factories/renderers, must write no compiled SQL, and must not
  leak rendered environment values; factory-returned adapter metadata that
  differs from the literal profile `type` must fail before renderer selection,
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
- include parsed DSN component and derived-fragment redaction cases before
  creating or splitting the test-kit repository or claiming external adapter
  compatibility: username, password, host, path, query values, percent-decoded
  values, and substrings of rendered connection strings must not leak through
  diagnostic text, diagnostic codes, resource metadata, `rendering.adapter_type`,
  logs, run results, evidence, or adapter test snapshots,
- include diagnostic-code embeddings for unsafe config keys and rendered values,
  such as `RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and
  `RC12LEAK`, before creating or splitting the test-kit repository or claiming
  external adapter compatibility,
- preserve safe adapter diagnostic codes with incidental non-secret config-key
  substrings, such as `RC_ADAPTER_CAPABILITY_UNSUPPORTED`, before creating or
  splitting the test-kit repository or claiming external adapter compatibility,
- include core render-sql compile-validation blocked-metadata integration cases
  before creating or splitting any test-kit harness that drives core compile
  flows,
- include malformed adapter factory result, malformed factory diagnostic
  payload, missing or invalid adapter API version declaration, and malformed
  capability support-state cases before creating or splitting the test-kit
  repository,
- include public/shared rendering helper cases before creating or splitting the
  test-kit repository: when a helper or harness accepts both a resolved adapter
  and an explicit renderer, adapter API incompatibility and missing, malformed,
  exception-raising, or mismatched renderer `adapter_type` metadata must fail
  before `render_plan()` is invoked,
- include renderer-output and generated-artifact publication cases before
  creating or splitting the test-kit repository: empty renderer output, empty
  or malformed direct compiled SQL writer requests, later empty or malformed
  rendered SQL batch requests, invalid later rendered steps, unsafe path
  segments, exact output paths that already exist as directories or other
  non-files, duplicate step names, and case-insensitive output collisions must
  fail before any compiled SQL directory or file is published,
- include rendered SQL step `required_capabilities` enforcement cases before
  creating or splitting the test-kit repository, introducing a renderer registry,
  publishing `recon-duckdb`, or claiming external adapter compatibility:
  current Core render-sql orchestration enforces these before SQL publication,
  and future shared conformance must preserve unsupported, not-implemented,
  unknown, versioned, malformed, or extra step-level capability declarations
  failing clearly before SQL artifacts, run results, evidence, or adapter test
  snapshots are published,
- include sanitized adapter factory exception and sanitized capability
  declaration exception cases before creating or splitting the test-kit
  repository or publishing external adapter compatibility claims,
- include adapter setup failure cases that assert no compiled SQL output,
  blocked compiled-check metadata, preserved diagnostics when factories return
  both adapters and diagnostics, de-duplicated repeated same-connection service
  diagnostics, preserved distinct source/target connection diagnostics, and
  preserved independent render diagnostics from otherwise resolvable contracts
  when setup diagnostics also exist before creating or splitting the test-kit
  repository or publishing external adapter compatibility claims,
- include result/evidence sink capability conformance before adapters claim
  write/sink compatibility: unsupported, unknown, malformed, version-mismatched,
  unsafe destination, missing schema, migration failure, partial write, retry,
  idempotency, retention, and required-sink failure cases must fail or report
  through locked sink-write status without falling back silently,
- include probabilistic summary capability conformance before adapters claim
  Bloom/sketch-like support: canonical composite-key serialization,
  partition/window scope, bidirectional summary build/probe/compare lifecycle,
  false-positive policy, intermediate summary cleanup/storage, and
  exact-confirmation requirements must be tested,
- include native SQL optimization and dialect validation conformance before
  production warehouse adapters claim execution compatibility: adapters must
  render from typed operation payloads, not authored YAML strings; generated SQL
  must avoid untyped `select *` comparison plans, naive full-row joins,
  unbounded source/target row movement, hidden Python fallback, and implicit
  partition/window filtering; shared tests must include adapter-native SQL
  snapshots, optional dialect syntax validation, and semantic comparison
  coverage for the capabilities the adapter claims,
- include scan-cost and query-plan safety conformance before production
  adapters claim execution compatibility for operations that may scan broad
  source or target relations,
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
  the applicable milestone design prework gate.

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
- large-result movement through artifact or sink references instead of embedding
  raw rows in run-result artifacts,
- masking and redaction policies,
- evidence templates,
- approval/sign-off artifacts,
- richer report levels,
- optional evidence vault integration boundaries.

Required gate:

- resolve the advanced evidence, redaction, templates, and sign-off gate in
  the applicable milestone design prework gate,
- resolve the failure detail JSONL and large result handling gate before adding
  non-CSV or streaming failure-detail formats,
- resolve exact-confirmation behavior before probabilistic suspected missing or
  extra records can drive large failure-detail export,
- define chunking, pagination, retention, cleanup, privacy, retry/idempotency,
  and large-store failure behavior before adding external large-result stores.

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

Boundary:

- this milestone owns the Hub and broad integration foundation,
- concrete event export, local agent tool surfaces, and action/remediation
  integrations are owned by the decimal milestones below,
- integrations must call public CLI, artifact, adapter, package, Hub, result,
  or evidence contracts rather than private internals.

Build:

- Recon Hub index metadata,
- CI action integration,
- orchestrator provider/operator,
- workflow provider integration,
- transformation framework integration patterns,
- data catalog and issue/ticket integration boundaries.

Required gate:

- resolve the Hub and external integrations gate in
  the applicable milestone design prework gate.

Recommended commit message:

```text
docs: define hub index metadata
```

## Post-MVP Milestone 32.1: lineage and observability event export

Build this after run, check, contract, result, and evidence metadata are stable
enough for external systems to consume without redefining Recon semantics.

Goal:

- export Recon run, check, contract, and evidence metadata safely to external
  observability, lineage, catalog, orchestration, or event systems.

Build:

- versioned event schema,
- run/check/contract identifiers,
- safe evidence links,
- retry and idempotency rules,
- local/offline export mode,
- external sink configuration boundaries,
- privacy classification for relation, owner/team, row-count, aggregate, and
  failure-summary metadata.

Do not build:

- raw row, key, value, credential, rendered profile, raw SQL, or native database
  error export by default,
- sink-specific behavior that changes core result or evidence semantics.

Required gate:

- resolve Gate 6F: Lineage And Observability Event Export Safety in the
  applicable milestone design prework gate,
- resolve Gate 6 source/target data privacy and ADR 0022 before exported event
  payloads include relation metadata, owner/team metadata, row counts,
  aggregate values, failure summaries, evidence links, or any other potentially
  sensitive run metadata.

Recommended commit message:

```text
feat: export observability events
```

## Post-MVP Milestone 32.2: optional local Recon MCP server and agent tool interface

Build this after CLI and Python command surfaces are stable enough to expose
through a structured local tool interface.

Goal:

- provide an optional local, non-hosted tool surface around safe Recon APIs for
  coding agents and local developer workflows.

Build:

- local-only server boundary,
- package or command shape,
- tool list and stable input/output schemas,
- tool classification for read-only, expensive, state-changing, row-scanning,
  file-writing, contract-writing, and remediation actions,
- project/profile access rules,
- redacted diagnostics and stable tool result schemas,
- explicit confirmation requirements for tools that scan rows, write artifacts,
  mutate contracts, or trigger actions.

Do not build:

- a hosted agent service,
- default state-changing tools,
- unapproved row-data scanning,
- contract-writing or remediation tools without separate gate coverage.

Required gates:

- resolve Gate 5H: Local MCP Tool Surface, Permissions, And Agent Action
  Safety,
- resolve Gate 4L for any row-scanning tool,
- apply Gate 6 privacy rules for all diagnostics and tool output,
- resolve Gate 6D before any action/remediation tool is exposed.

Recommended commit message:

```text
feat: add local recon mcp interface
```

## Post-MVP Milestone 32.5: workflow actions and remediation integrations

Build this only after run results, evidence, integration boundaries, and
permission rules are stable.

Goal:

- support explicit, approval-first workflow actions without letting Recon become
  an unsafe autonomous actor.

Build:

- webhooks, tickets, notifications, remediation hooks, and approval workflows,
- allowed and forbidden action types,
- dry-run behavior,
- approval and permission model,
- idempotency, retry, audit log, rollback, and failure-status behavior,
- links from actions back to run and evidence artifacts,
- explicit policy for whether actions may modify contracts, baselines, or
  warehouse state.

Do not build:

- destructive or self-healing defaults,
- automatic tolerance, contract, warehouse, dashboard, deployment, or baseline
  updates from inferred business behavior,
- action triggers from scorecards, baselines, MCP tools, or AI assistants before
  this gate is satisfied for that surface.

Required gate:

- resolve Gate 6D: Actionable Sink And Remediation Safety in the applicable
  milestone design prework gate.

Recommended commit message:

```text
feat: add remediation actions
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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

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
  the applicable milestone design prework gate.

Recommended commit message:

```text
docs: define domain package boundaries
```

## Post-MVP Milestone 42: semantic and AI-assisted comparison packages

Build this only after core exact comparison, evidence, package compatibility,
privacy, adapter conformance, and result wording are stable.

Goal:

- allow optional semantic, vector, fuzzy, model-judged, or business-semantic
  comparison packages without making non-exact similarity a default core
  equivalence claim.

Build:

- explicit package boundary outside default core exact checks,
- supported method taxonomy,
- threshold calibration and labeled evaluation requirements,
- model/provider/version and embedding/version metadata where applicable,
- false-positive and false-negative reporting,
- deterministic fallback behavior,
- cost and privacy controls for text sent outside the local project,
- result and evidence wording that clearly says non-exact comparison.

Do not build:

- default core semantic comparison,
- exact-equivalence wording for similarity or model-judged checks,
- model calls without provider, version, budget, privacy, and output-validation
  policy.

Required gates:

- resolve Gate 9A: Semantic, LLM, And Embedding Comparison Safety,
- resolve Gate 9 when a semantic package calls a model provider,
- resolve Gate 3M when semantic or model-assisted candidates generate checks.

Recommended commit message:

```text
feat: add semantic comparison packages
```

## Post-MVP Milestone 42.5: optional Recon AI assistant package

Build this only after deterministic discovery, suggestion, package, MCP,
action, privacy, and semantic-package boundaries are mature enough to keep AI
output advisory and auditable.

Goal:

- provide an optional bring-your-own-model assistant package for advisory Recon
  suggestions outside `recon-core` default behavior.

Build:

- optional package boundary,
- provider abstraction and bring-your-own-key behavior,
- model and prompt version tracking,
- token and cost budgets,
- prompt privacy policy,
- structured output validation,
- failure fallback behavior,
- explicit user approval flow for generated contract edits, actions, or
  suggestions.

Do not build:

- model/provider dependency in `recon-core`,
- hidden chain-of-thought reliance,
- automatic contract mutation,
- automatic remediation or baseline updates,
- sending raw rows, credentials, rendered profiles, raw SQL, or sensitive
  project metadata without an explicitly approved opt-in policy.

Required gates:

- resolve Gate 9: AI Assistant Provider, Prompt, And Model Governance,
- resolve Gate 3M for generated check candidates,
- resolve Gate 6D for assistant-proposed actions or fixes,
- resolve Gate 9A if the assistant performs semantic comparison.

Recommended commit message:

```text
feat: add optional ai assistant package
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
- user-facing agent onboarding pack and installer,
- metadata discovery, data profiling, contract suggestions, and relation scope
  selection,
- CDC execution and asymmetric delete representation,
- advanced CDC modes such as operation-column CDC, update propagation, operation
  count diff, tombstone CDC, and SCD2 CDC,
- historical profiles, drift, and statistical baseline checks,
- quality rollups, ownership, and SLA scorecards,
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
- lineage and observability event export,
- optional local Recon MCP server and agent tool interface,
- workflow actions and remediation integrations,
- semantic and AI-assisted comparison packages,
- optional Recon AI assistant package,
- source-location diagnostic ranges,
- orchestration integrations.

## Design principle

Build the smallest complete loop first, then widen capability.
