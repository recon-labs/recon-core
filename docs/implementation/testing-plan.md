# Testing Plan

## Purpose

This document defines the implementation testing plan for Recon Core.

Tests should protect public behavior and prevent misleading evidence.

## Milestone test planning

Every milestone test plan should follow
`docs/planning/milestone-process.md` and be derived from the milestone prework
artifact. For normal or low-risk milestones, the test plan must cover the
documented scope, expected behavior, non-goals, and Definition of Done.

High-risk milestones and public-surface changes must map tests to a
dimension-expanded acceptance/conformance matrix before implementation. Each
required matrix row must map to a new test, an existing test, or an explicit
out-of-scope rationale. Matrix examples are not complete coverage unless the
relevant dimensions and sibling variants are enumerated.

When a milestone is split into decimal sub-milestones, each sub-milestone needs
its own test plan and, when high-risk, its own conformance matrix. Do not use the
umbrella milestone as the implementation test boundary.

## Test layers

### Unit tests

Fast tests for pure functions and small models.

Examples:

- config defaults,
- path resolution,
- name validation,
- tolerance precedence,
- schema ignore matching,
- sampling precedence.

### Parser tests

Tests for authored YAML.

Examples:

- one contract per file,
- multiple contracts per file,
- duplicate contract names,
- missing source/target,
- invalid YAML,
- invalid YAML diagnostics do not expose raw parser snippets, source/target
  query text, credentials, or other private literals from the offending file,
- unknown fields.

Milestone 4.6 resource-indexing tests should cover:

- missing default optional non-contract paths are skipped,
- explicitly configured missing optional paths fail with
  `RC_PARSE_RESOURCE_PATH_NOT_FOUND`,
- catalog entries with `explicit_missing_is_error: false` skip missing authored
  paths,
- non-contract source-file discovery is deterministic,
- overlapping configured paths deduplicate by real path,
- file checksums are stable,
- macro files are indexed only as `macro_file` source files,
- index-only non-contract YAML files are not parsed as named resources,
- endpoint files are not loaded before `endpoint-paths` is implemented.

### Compiler tests

Tests for explicit generated behavior.

Examples:

- stable compiled IDs,
- compiled model serialization,
- check packs expand,
- metrics compile into checks,
- columns do not create checks,
- empty check pack errors,
- sampling resolves per check,
- tolerances resolve by precedence,
- schema policies apply,
- CDC config validates.
- typed check plans include expected operations,
- compiled artifacts reference typed plans and rendered SQL.

### Validation tests

Each locked validation rule should have tests.

Milestone 5 validation tests should assert the diagnostic code, severity, and
phase ownership defined in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.
Future validation expansions for sampling, tolerance, columns, check-pack
config, resource references, adapters, results, or evidence should lock their
rule-specific diagnostics before implementation and test those diagnostics
explicitly.

Check-pack invocation config tests should follow ADR 0018. Before accepting
`config`, `on_empty: warn`, or `on_empty: skip`, tests should cover typed
invocation parsing, schema validation, unknown keys, duplicate invocations,
empty-expansion diagnostics, precedence, and compiled artifact visibility.

Column and value-comparison tests should follow ADR 0019. Current typed column
validation tests should cover duplicate declarations, unknown categories,
undeclared references, invalid selectors, and check/category incompatibility.
Before accepting column-level eligibility, unused-column warnings, all-column
expansion, resolved column metadata, adapter metadata validation, or row-level
value checks, tests should cover those behaviors explicitly.

Tolerance, null, and normalization tests should follow ADR 0009. Before
accepting policy resolution or execution, tests should cover numeric shorthand
and object equivalence, invalid tolerance shapes, unsupported relative or
timestamp tolerance in the current milestone, invalid null policy values,
invalid or duplicate null sentinels, invalid normalization steps, invalid or
unsupported MVP regex, adapter capability blocking for regex-dependent
execution, type incompatibility, precedence, and resolved policy artifact
visibility.

Rules include:

- no silent all-column comparison,
- row-level checks require keys,
- duplicate keys block dependent row-level value checks,
- null keys block dependent row-level value checks,
- CDC propagation checks require CDC keys,
- `basic_equivalence` without grain fails validation,
- invalid check/column types error,
- random sampling requires persisted keys,
- hash sampling does not assume portability,
- schema ignores are explicit,
- CDC mode is required for CDC checks.

### Check engine tests

Tests for built-in checks.

Examples:

- row count pass/fail,
- missing keys,
- extra keys,
- duplicate source keys,
- duplicate target keys,
- sum diff,
- grouped aggregate diff later.

Milestone 7 is split and should not be tested as one umbrella implementation
unit. Each sub-milestone below needs its own final test plan and phase exit
review before coding, but these rows assign the required coverage so no test
expectation remains owned only by umbrella Milestone 7.

Milestone 7 BDD/workflow scenarios:

| Scenario | Sub-milestone | Expected behavior | Planned coverage |
| --- | --- | --- | --- |
| Compiled checks are loaded but adapter execution is still out of scope. | 7.1 | Recon reports explicit `blocked` or `not_executable` status without implying checks ran. | Service/model tests for result status, prerequisite/blocking metadata, and diagnostics. |
| A relation-backed DuckDB row-count check passes, fails, or errors. | 7.2 | Recon executes only the row-count operation through the selected literal adapter connection and emits sanitized diagnostics/results. | Service and adapter lifecycle tests with pass, fail, setup failure, runtime error, and privacy assertions. |
| Null, duplicate, missing, or extra grain-key checks run before dependent row-level value checks. | 7.3 | Key-safety results are explicit; null or duplicate keys block dependent future row-level checks instead of allowing misleading comparison evidence. | Key-check execution tests plus prerequisite/blocking tests for dependent row-level value checks. |
| Ungrouped and grouped `sum` metric checks compare aggregates with numeric tolerance. | 7.4 | Aggregate checks execute only current compiled `sum` plans and report pass/fail/error with explicit empty-result and type-mismatch behavior. | Aggregate execution tests for ungrouped/grouped sums, tolerance, empty aggregates, and type mismatches. |

Milestone 7 split acceptance/conformance matrix:

| Dimension | Cases | Expected behavior | Test coverage | Docs or gate impact | Out-of-scope rationale |
| --- | --- | --- | --- | --- | --- |
| Check-engine boundary and result model | Result status taxonomy, reason-code taxonomy, prerequisite/blocking representation, unsupported or not-yet-executable checks, empty compiled-check scope, diagnostic preservation. | Results preserve status, reason code, diagnostic code, severity, message, path, resource context, and hint; non-executed checks are explicit and cannot look like passing evidence. Empty compiled-check scope aggregates to `no_checks` and maps to command-level `RC_RUNTIME_NO_COMPILED_CHECKS`. Known later-phase operations use `not_implemented_in_current_phase`; unknown valid operation types use `unsupported_typed_operation`; declared unavailable engine capabilities use `missing_engine_capability`; malformed operation payloads are artifact-invalid diagnostics. | 7.1 unit/service tests for result serialization, blocked/prerequisite metadata, `not_executable` reason codes, `no_checks` aggregation and command mapping, later-phase versus unsupported-operation and missing-capability mapping, and diagnostics. | `docs/implementation/mvp-build-order.md`, result-model docs, diagnostic output conformance gate. | Adapter execution, generated run results, evidence, reports, and failure details remain Milestones 7.2, 8, and 9. |
| Internal dispatch versus public check registry | Already compiled check types, internal dispatch mapping, explicit authored `checks: [...]` still unsupported. | Internal dispatch may route compiled checks, but public authored check registry behavior does not become supported silently. | 7.1 unit tests for dispatch of compiled check types and unsupported authored checks. | Explicit authored checks/check registry gate. | Public explicit authored checks remain future scope until their gate and docs are resolved. |
| Adapter execution lifecycle | Literal adapter `type`, selected profile/target, referenced connections, adapter API metadata, setup failures, same-context execution. | Execution loads only referenced profile connections, preserves literal type routing, validates adapter metadata/API, and fails setup safely with sanitized diagnostics. | 7.2 service/adapter tests for profile loading, adapter resolution, lifecycle, setup failure, and same-context enforcement. | Adapter/Profile Diagnostic Conformance Gate and adapter API compatibility docs. | Query endpoints, cross-adapter execution, and cross-connection comparison remain future/gated. |
| Adapter/profile diagnostic privacy | Unsafe rendered profile keys or values in code, message, hint, path, resource metadata, line/column, and future structured fields. | Unsafe profile-backed diagnostic data is redacted or replaced with safe actionable diagnostics before public output. | 7.2 redaction tests for runtime adapter/profile diagnostics, including short numeric and transformed values where applicable. | Adapter/Profile Diagnostic Conformance Gate; source/target data privacy gate for runtime surfaces. | Evidence/report/failure-detail redaction remains Milestone 9 unless execution output introduces that surface earlier. |
| Row-count execution | Pass, fail, adapter setup failure, runtime adapter error, database error, row count value visibility. | Row-count checks execute through adapter pushdown only where explicitly supported; public output follows the source/target privacy policy. | 7.2 row-count tests for pass/fail/error and sanitized output. | Comparison execution placement strategy and source/target privacy gate. | Run-result artifact writing remains Milestone 8. |
| Grain-key null and duplicate checks | Source null keys, target null keys, source duplicate keys, target duplicate keys, sampled contracts. | Null and duplicate grain-key results are explicit; sampling does not remove non-null or uniqueness requirements. | 7.3 execution tests for each side and sampled/non-sampled cases. | Key semantics ADRs, source/target privacy gate, sampling safety rules. | Raw key examples and failure exports remain evidence/failure-detail scope. |
| Missing and extra key checks | Source-minus-target missing keys, target-minus-source extra keys, type mismatch, nullable keys. | Missing/extra key checks fail clearly or report mismatches without inferred mappings, silent coercion, or misleading empty output. | 7.3 execution tests for missing/extra keys, mismatched key types, and prerequisite interactions. | Comparison execution placement strategy and no silent mapping/coercion rules. | Row-level value comparison remains later scope. |
| Dependent row-level check blocking | Null grain keys, duplicate grain keys, missing prerequisite results, future row-level value checks. | Dependent row-level value checks are blocked when source or target grain keys are null or non-unique. | 7.3 prerequisite/blocking tests; no value comparison execution required. | Locked key semantics and high-risk phase exit review. | Implementing row-level value checks remains a later milestone. |
| Aggregate metric execution | Ungrouped `sum_diff`, grouped aggregate diff, numeric tolerance, empty aggregates, aggregate type mismatch. | Current compiled `sum` plans execute with explicit tolerance, empty-result, and type-mismatch semantics. | 7.4 aggregate tests for pass/fail/error, grouped/ungrouped, tolerance, empty input, and type mismatch. | Typed operation catalog re-check; comparison execution placement; source/target privacy gate. | Timestamp/string tolerance, normalization, schema policy, and new metrics remain future scope. |
| Public output and generated artifacts | Terminal output, diagnostics, logs, run-result artifacts, evidence/report/failure-detail links. | Milestone 7 public output is limited to assigned execution/result surfaces; no generated run-result/evidence artifacts appear before Milestones 8 and 9. | 7.1-7.4 negative tests for absent `target/run_results.json`, evidence, report, and failure-detail output unless scope changes. | Generated artifact lifecycle gate; Milestone 8 and 9 boundaries. | `target/run_results.json` belongs to Milestone 8; evidence/report/failure details belong to Milestone 9. |
| Execution placement and no silent fallback | Row count, key checks, aggregate checks, unsupported placement, missing capability, materialization requested too early, third-engine comparison requested too early, and in-memory/Python fallback temptation. | Each executing sub-milestone uses only its locked placement strategy. Unsupported or unavailable placement fails with explicit blocked/not-executable diagnostics rather than silently changing execution engine. | Pre-7.2, 7.3, and 7.4 placement tests for supported pushdown, unsupported placement, missing capability, and no fallback/materialization cases. | ADR 0021 and comparison execution placement gate. | Generic placement syntax, staging/materialization, third-engine comparison, and fallback policies remain future scope unless separately designed. |

The final Milestone 7.1 acceptance/conformance matrix, edge-case matrix, and
BDD workflow scenarios live in `docs/planning/milestone-7-1-prework.md`. The
same prework artifact also contains the 7.1 gate satisfaction proof and
phase-exit checklist, plus the exact future implementation file/test map.

Future result, evidence, state, sink, probabilistic, and adapter conformance matrix:

| Dimension | Owning milestone | Cases | Expected behavior | Test coverage | Docs or gate impact | Out-of-scope rationale |
| --- | --- | --- | --- | --- | --- | --- |
| Local run-result artifact | 8 | Run metadata, placement metadata, adapter/capability status, artifact references, sink-reference placeholders, terminal summary, exit codes, diagnostic preservation, privacy defaults, whole-project scope metadata that can later represent selected scope. | `target/run_results.json` is the first local machine-readable result artifact and records safe metadata without writing evidence, result tables, state, or external sinks. It must not bake in whole-project-only assumptions that would make future selected-scope runs misleading. | Runner/result artifact tests for pass, fail, error, blocked, diagnostic preservation, privacy redaction, local artifact path/versioning, scope metadata, and no sink writes. | Generated artifact lifecycle gate, selector-readiness gate, ADR 0021 placement metadata, ADR 0022 result/evidence boundary. | Evidence reports, failure details, result tables, state, and selector execution remain later milestones. |
| Basic local evidence and failure details | 9 | Local report, bounded failure detail, disabled local output, local-only mode, terminal-only mode, truncation, masking/redaction, artifact references, evidence links, whole-run scope wording that can later represent selected scope. | Evidence output is explicit, optional according to locked mode, bounded by default, privacy-safe, and separate from table-backed sinks or state. Evidence wording must not imply unselected contracts/checks were reconciled once selector-scoped runs exist. | Evidence writer tests for generated local artifacts, disabled output, row limits, masking/redaction, truncation, safe diagnostics, artifact links, scope wording, and no table/state writes. | ADR 0022, source/target privacy gate, generated artifact lifecycle gate, selector-readiness gate. | Production result/evidence table sinks, external large stores, database-backed state, and selector execution remain later milestones. |
| Minimal contract/path selectors | 10.6 | Contract selector, exact project-relative path selector, nested contract files, multi-contract YAML file selection, metric-generated checks inside selected contracts, optional contract exclusion, optional simple contract-name pattern exclusion such as `contract:experimental_*`, compile, SQL rendering, run, selected-scope metadata, empty selection, invalid selector method, unsupported resource kind. | Early selectors operate only on explicit contract/path scope and fail clearly for unsupported syntax. `path:...` uses manifest paths, not independent filesystem scans. Selecting a multi-contract file includes all contracts in that file unless later composition narrows it. Contract exclusion and simple contract-name patterns are included only if the selector gate locks pattern syntax and select/exclude precedence. Generated artifacts, terminal output, run results, and evidence references identify the selected scope. | CLI/service tests for `compile --select`, `compile --render-sql --select`, `run --select`, `run --exclude` when admitted, nested paths, multi-contract files, metric-generated checks, invalid syntax, no matches, unsupported method, artifact cleanup, and selected-scope metadata. | Selector semantics gate, generated artifact lifecycle gate, artifact freshness gate, compatibility matrix. | `selectors.yml`, named selectors, check-level selectors, tag/domain/package selectors, state/result selectors, graph operators, directory-prefix path selection, and partial parse remain later scope. |
| Rich selector expansion | 19 | Named selectors such as `selector:critical_reconciliations`, check-level selection such as `check:customer_revenue.row_count`, richer select/exclude composition, contract-pattern exclusion not admitted into the minimal selector subset, optional tag/domain/package selectors, optional state/result selectors after supporting artifacts exist, selected-scope metadata across generated outputs. | Rich selectors build on the minimal selector surface without changing existing selector meaning or making partial artifacts/evidence look like whole-project results. | Selector parser and resolver tests, CLI composition tests, artifact freshness and cleanup tests, run/evidence scope tests, empty/invalid selector diagnostics, and compatibility regression tests for minimal selectors. | Selector semantics gate, generated artifact lifecycle gate, state/run-result compatibility gates when state/result selectors are included. | Transformation-style graph selection, dependency expansion, or state/result selectors remain out of scope until their supporting project graph, state, and result artifacts are stable. |
| Sampling and probabilistic key coverage | 24 and 26 when used for sampling or CDC | Bloom/sketch-like summary build, transport/storage, probe, compare, cleanup, false-positive policy, false-negative prohibition, canonical composite-key serialization, partition/window scope, bidirectional A-to-B and B-to-A probing, exact-confirmation behavior. | Probabilistic summaries never look exact unless exact confirmation runs. Suspected missing/extra records use explicit wording and cannot drive raw failure-detail export without the locked confirmation policy. | Sampling/CDC tests only after Gate 4K: deterministic serialization, partition/window isolation, bidirectional probing, false-positive safeguards, cleanup, privacy, and exact-confirmation gates. | Gate 4K plus ADR 0021/0022 follow-up, sampling execution gate, CDC implementation gate, adapter capability gates. | No Bloom/sketch behavior is required for Milestone 7.1, 7.2, 7.3, 7.4, 8, or 9 unless explicitly re-split. |
| State, watermarks, and persisted samples | 25 | Local state format, watermark bootstrap, advancement, rollback/retry, persisted sample keys, previous-failure keys, versioning, recovery, state/result/evidence separation. | Recurring validation state is explicit, versioned, reproducible, and not confused with result tables or evidence sinks. | State backend tests for bootstrap, advancement, failed-run behavior, persisted samples, previous-failure state, versioning, recovery, and no result/evidence sink writes. | State/watermark gate and compatibility docs. | Remote or database-backed state remains Milestone 37; production result tables remain 25.5. |
| Production result tables and sink writes | 25.5 | Source, target, or third configured destination, sink requiredness, unsupported/missing/malformed capability, unsafe destination config, schema versioning/migration, append/upsert semantics, idempotency, retry, partial write, retention, sink-write status, privacy. | Table-backed result/evidence sinks write only when explicitly configured and adapter-supported. Sink failures are distinguishable from reconciliation failures and never fall back silently to local-only success. | Sink writer tests for each destination class, capability mismatch, unsafe config, migration failure, partial write/retry/idempotency, retention, required/optional sink behavior, privacy, and sink status. | ADR 0022, result table writer gate, adapter write/sink conformance gate. | No table sink writes before 25.5; adapter packages cannot claim sink compatibility before Milestone 29 conformance. |
| Adapter write/sink conformance | 29 | Adapter API support states, write capability declarations, result/evidence table writes, schema migration hooks, required sink failure behavior, privacy-safe diagnostics, unsupported/unknown/malformed states. | Shared adapter conformance proves write/sink behavior before external adapters claim compatibility. Unsupported or malformed support fails clearly before data movement. | Shared adapter test-kit rows for write/sink APIs, capability support states, schema migration, destination validation, sanitized diagnostics, and no silent fallback. | Gate 8 plus ADR 0022 and capability catalog updates. | Adapter package split can proceed only after the relevant conformance surface is locked. |
| Adapter probabilistic-summary conformance | 29 | Summary build/probe/compare APIs, canonical composite-key serialization, hash/canonicalization rules, partition/window scope, intermediate storage/cleanup, false-positive policy, exact-confirmation hooks, privacy. | Adapters cannot claim Bloom/sketch-like support until shared tests prove deterministic, privacy-safe, bounded behavior and clear exact/probabilistic result semantics. | Shared adapter test-kit rows for summary lifecycle, serialization compatibility, bidirectional probing, cleanup, capability mismatch, and exact-confirmation signaling. | Gate 4K, Gate 8, ADR 0021/0022 follow-up, capability catalog updates. | Probabilistic support is optional and future-gated; exact checks remain the default safe path. |
| Advanced evidence and large-result stores | 31 | JSONL/streaming failure details, pagination, chunking, row limits, truncation, external store references, retry/idempotency, cleanup, retention, masking/redaction, exact-confirmation before probabilistic export. | Large mismatch sets move through bounded artifacts or sink references, not embedded run-result rows. Large-result failures report separately from reconciliation failures. | Advanced evidence tests for JSONL/streaming, pagination/chunking, truncation, privacy, external reference metadata, cleanup, retries, retention, and exact-confirmation gating. | Gate 6C, ADR 0022, advanced evidence gate. | Basic local evidence remains Milestone 9; production result tables remain 25.5. |

### Adapter tests

Base adapter tests should cover:

- adapter API version compatibility,
- capability declarations,
- metadata shape,
- relation existence,
- query execution,
- quoting,
- limit compilation,
- typed operation rendering,
- unsupported capability diagnostics.

Adapter tests for key-dependent operations should cover null-key detection,
duplicate-key detection, key-diff rendering, and CDC-key operation rendering
where supported.

The in-core DuckDB SQL renderer semantic tests must be gated in CI with the
optional DuckDB extra installed. The required CI path should install
`.[dev,duckdb]`, set `RECON_REQUIRE_DUCKDB_TESTS=1`, and run
`tests/adapters/test_duckdb_sql_renderer.py` so optional dependency coverage
cannot silently skip the SQL comparison cases that protect no-coercion and exact
numeric behavior.

Future shared adapter test-kit and adapter-repository semantic jobs must follow
the same rule: required capability conformance jobs install the adapter package
or optional extra under test and fail when the dependency is missing or
unimportable. Local developer convenience skips are acceptable only outside
required conformance gates.

Production adapters should eventually use a shared adapter test kit. The same
test kit should run in every adapter repo and should include operation-rendering
golden tests.

The shared adapter test kit should include adapter API conformance tests
separate from SQL comparison conformance. These tests should verify adapter
registry and factory behavior, including that a factory returning neither an
adapter nor diagnostics, or returning a malformed resolution result, fails with
`RC_ADAPTER_RESOLUTION_FAILED` instead of allowing adapter-aware rendering or
execution to succeed. Malformed diagnostic containers or entries inside a
factory resolution result are malformed resolution results and must also fail
with `RC_ADAPTER_RESOLUTION_FAILED` before diagnostic redaction, rendering, or
artifact-writing, or execution consumes them. Malformed field values are part
of this boundary: representative conformance cases should include a string
severity such as `"error"` instead of `DiagnosticSeverity`, empty or non-string
`code` or `message`, non-string optional context fields, and non-integer
`line` or `column` values. The same conformance suite should verify that missing
or invalid adapter API version declarations fail with
`RC_ADAPTER_API_VERSION_UNSUPPORTED`, malformed capability support states become
structured diagnostics, invalid or exception-raising `adapter_type` metadata
fails with `RC_ADAPTER_METADATA_INVALID`, profile `type`/adapter metadata
mismatches fail with `RC_ADAPTER_TYPE_MISMATCH`, empty renderer output fails
with `RC_ADAPTER_RENDERED_SQL_EMPTY`, malformed non-empty renderer output fails
with `RC_ADAPTER_OPERATION_RENDER_FAILED`, including unsafe or duplicate
renderer step names, public/shared rendering helpers that accept explicit
renderers fail before rendering when adapter API compatibility fails or the
renderer `adapter_type` is missing, malformed, exception-raising, or different
from the resolved adapter type, and adapter factory exceptions, adapter metadata
exceptions, and capability declaration exceptions become sanitized structured
diagnostics instead of raw exceptions that can leak rendered profile keys or
values.
Malformed renderer-output coverage must include invalid later rendered steps
and case-insensitive output collisions, and artifact writer tests must prove
direct empty or malformed rendered SQL writer requests and later empty or
malformed rendered SQL batch requests fail before any compiled SQL directory or
file is created. Artifact preflight tests must include exact output paths that
already exist as directories or other non-files, including overwrite-enabled
calls. Batched artifact writer tests must prove the full batch is validated and
preflighted before the first compiled SQL file is written. Current Core tests
cover `RenderedSql.required_capabilities` as executable requirements before SQL
publication. Shared renderer and adapter-repository tests must preserve and
expand that coverage: supported step-level capabilities pass, while unsupported,
not-implemented, unknown, versioned, malformed, or extra renderer-declared
capabilities fail clearly before SQL artifacts, run results, evidence, or
adapter test snapshots are published.
Factories that return both an adapter and diagnostics, or both an adapter and
malformed diagnostics, should be treated as setup failures; the returned adapter
must not be used for rendering or execution.
Adapter setup failure cases must also verify that adapter-aware compile writes
no compiled SQL, marks affected compiled checks blocked with structured
diagnostics, de-duplicates repeated same-connection setup diagnostics in service
and CLI output, and preserves distinct source/target connection setup
diagnostics. They should also prove that adapter setup diagnostics do not hide
render diagnostics from otherwise resolvable contracts in the same
adapter-aware compile invocation.

Profile-backed diagnostic redaction tests must include DSN component and
derived-fragment cases, not only whole rendered connection strings. Required
cases include username, password, host, path, query values, percent-decoded
values, and substrings appearing independently in diagnostic code, message,
hint, path, `resource_type`, `resource_name`, `line`, `column`,
`rendering.adapter_type`, logs, run results, evidence, and adapter test
snapshots for every surface that claims compatibility.

Adapter-aware compile tests should also cover the core-owned case where compile
validation fails before adapter rendering starts. When `--render-sql` was
requested, otherwise renderable checks must be marked `blocked` with
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, compiled SQL must not be
written, and adapter factories/renderers must not be invoked. A future shared
adapter test kit only needs this case when it drives core compile flows; pure
adapter API conformance should reference the core artifact requirement instead
of duplicating compiler validation tests.

The same adapter API conformance suite must satisfy the Adapter/Profile
Diagnostic Conformance Gate in `docs/compatibility/adapter-api.md` before
adapter execution, connection debug or profile validation commands, external
adapter repositories, or compatibility claims rely on rendered profiles. It
should verify selected profile/target loading, referenced-connection filtering,
missing environment variables,
environment-variable defaults, `{{ env_var(...) }}` and bare `env_var(...)`
forms in non-routing connection fields, unsupported template syntax including
`{{ ... }}`, `{% ... %}`, and `{# ... #}`, unsupported bare env-var
expressions, embedded env-var calls, filters, literal adapter `type` handling,
and adapter diagnostics returned after rendered profile config is available.
Unsupported env-var/template cases should verify that invalid syntax fails
before adapter resolution and does not survive as literal connection config.
Literal adapter `type` cases should verify that connection `type` is a
non-empty literal string; `{{ ... }}`, `{% ... %}`, `{# ... #}`, or
`env_var(...)` in `type` fails profile config before adapter resolution;
adapter factories and renderers are not invoked; compiled SQL is not written;
and the rendered environment value does not appear in diagnostics or artifacts.
Adapter choices
that vary by environment should be represented by separate selected targets or
separate named connections, each with a literal `type`, not by rendering the
adapter type from environment variables.
Factory, optional dependency, API compatibility, capability, metadata,
rendering, and execution diagnostics should be tested as public output and must
not leak rendered connection config keys or values classified as unsafe for
diagnostics. Adapter API compatibility diagnostics are part of this
conformance surface because they can be derived from profile-backed adapter
instances; render-phase diagnostics and `rendering.adapter_type` metadata are
part of the same surface. Adapter diagnostic conformance tests should also
assert that adapter-provided diagnostics include safe non-empty messages and
that core redaction replaces unsafe message text with a generic safe message
instead of dropping the message field. Redaction tests should include
case-variant and simple transformation cases, including uppercase or lowercase
config keys, non-string rendered values, case-changed rendered values, DSN
substrings, tokens, and passwords appearing independently in diagnostic
`code`, message, hint, path, `resource_type`, `resource_name`, `line`, `column`,
`rendering.adapter_type`, and any future structured diagnostic fields.
Diagnostic `code` cases must include unsafe config keys and rendered values in
both delimiter-separated and separatorless forms, such as `RC_PASSWORD_LEAK`,
`RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`. They must also verify
safe adapter diagnostic-code preservation for incidental non-secret config-key
substrings, such as `RC_ADAPTER_CAPABILITY_UNSUPPORTED`. Numeric field cases
must cover integer-valued `line` and `column` diagnostics as well as numeric
strings that match rendered scalar profile values. They must include short
numeric rendered scalars, for example `port: 12`, in diagnostic `code`,
diagnostic text, unsafe resource metadata, numeric `line`/`column`, and
`rendering.adapter_type`, so the suite proves exact short-token redaction and
not only long secret-like tokens. Short numeric scalar cases should include
alternate integer-equivalent representations such as `12.0`, `+12`, and
`1.2e1`. They must cover both directions: an integer-like profile scalar emitted
by an adapter as a decimal or scientific string, and a rendered numeric-string
profile scalar such as `"12.0"` or an env-var-rendered string emitted by an
adapter as `12`, `+12`, or `1.2e1`. Assertions should inspect the specific
public diagnostic or rendering fields under test rather than scanning whole
generated artifacts where checksums or stable IDs can contain unrelated short
numerals.

Before check execution, runner/results, evidence/reporting, debug commands, or
adapter test-kit execution surfaces are implemented or claimed compatible, add
source/target data privacy conformance tests. These tests should assert that
terminal output, logs, diagnostics, `run_results.json`, failure details,
reports, evidence, adapter runtime errors, database error text, and test
snapshots do not expose raw rows, comparison keys, normalized values, aggregate
values, row counts, relation names, query text, or other source/target context
unless the source/target data privacy policy explicitly classifies the output
as public or allows controlled export. Cases should cover pass, fail, error,
skipped, truncation, disabled failure export, masked/hash-only output, adapter
runtime errors, database errors, and raw adapter/database/runtime exception text
so a value suppressed in one public surface cannot leak through another.

Before creating, publishing, or splitting a shared adapter test-kit repository,
define a SQL comparison conformance matrix. The matrix should make comparison
semantics executable across adapters and should cover:

- null-safe equality,
- distinct non-null key-diff semantics,
- nullable grouped aggregate keys,
- no implicit type coercion or combination-casting matches,
- representative cross-type value cases such as numeric/string,
  boolean/numeric/string, decimal/float, and date/timestamp where supported,
- key-diff type mismatches fail instead of returning misleading missing/extra
  key rows,
- grouped aggregate key type mismatches fail with clear Recon or adapter-level
  errors instead of raw dialect binder errors,
- aggregate input column and value type mismatches fail instead of being
  compared through dialect implicit casts,
- same-type unsupported or non-numeric aggregate metric inputs fail with clear
  Recon or adapter-level errors instead of raw dialect binder errors,
- boolean aggregate inputs fail for `sum` semantics when an engine treats them
  as true-value counts instead of numeric aggregates,
- valid exact numeric aggregate inputs, including large integers and decimals,
  are not rounded or widened through lossy casts before comparison,
- unsigned large-integer aggregate inputs, such as DuckDB `UHUGEINT`, either
  prove exact aggregate comparison behavior or fail with clear adapter-level
  errors,
- empty aggregate result semantics are explicit before execution conformance is
  claimed, including cases where an engine returns `NULL` for `sum` on empty
  groups rather than zero, how two empty aggregate results compare, how empty
  aggregate `NULL` is distinguished from numeric zero, and how run
  results/evidence surface that distinction,
- empty source/target relations with mismatched key or group-key types still
  fail instead of producing empty trustworthy-looking comparison output,
- grouped aggregate renderers do not use cross-type coalescing for source and
  target group keys,
- same-context rendering requirements fail clearly when a renderer cannot safely
  bridge multiple connection configs,
- capability-specific behavior for unsupported casts, normalization, hashing,
  timestamp, semi-structured, or metadata-dependent comparisons,
- clear diagnostics or unsupported capability results when an adapter cannot
  safely perform a comparison.

### Artifact tests

Tests for generated artifacts.

Examples:

- manifest JSON shape,
- top-level artifact headers,
- compiled contract shape,
- compiled checks shape,
- invocation IDs included for compile and run artifacts,
- run results shape,
- diagnostics included,
- check requirements included,
- identity metadata included,
- blocked checks include `blocked_by` and a machine-readable reason code,
- render-sql requests blocked by compile validation use `rendering.status:
  blocked` with `RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, not
  `not_rendered`,
- artifact versions included.
- diagnostics preserve code, severity, message, path, resource context, and
  hint where available.

Manifest tests for resource indexing should assert that non-contract files are
included in `files` with path, `resource_type`, and checksum only, and that no
top-level parsed resource summaries are emitted before those schemas exist.

### CLI tests

Tests for command behavior.

Examples:

- `recon init`,
- `recon parse`,
- `recon compile`,
- `recon run`,
- exit codes,
- terminal summaries,
- failed commands print each diagnostic code and message, including profile,
  adapter, runtime, and evidence diagnostics as those phases are implemented.
- failed parse/config commands do not print raw YAML parser snippets,
  source/target query text, rendered profile values, credentials, or private
  literals from malformed authored files.

## Golden tests

Golden files can be used for compiled artifacts.

Use golden tests carefully so they verify public behavior without becoming brittle.

## Test fixtures

Fixtures should be small and deterministic.

Avoid real customer data.

Use fake business examples.

## Continuous integration

CI should run:

```text
format check
lint
type check
unit tests
parser tests
compiler tests
artifact tests
CLI tests
```

Adapter integration tests that require external services can run separately.

## Design principle

If a behavior can affect evidence trust, it needs tests.
