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
fails with `RC_ADAPTER_METADATA_INVALID`, empty renderer output fails with
`RC_ADAPTER_RENDERED_SQL_EMPTY`, malformed non-empty renderer output fails with
`RC_ADAPTER_OPERATION_RENDER_FAILED`, including unsafe or duplicate renderer
step names, and adapter factory exceptions, adapter metadata exceptions, and
capability declaration exceptions become sanitized structured diagnostics
instead of raw exceptions that can leak rendered profile keys or values.
Factories that return both an adapter and diagnostics, or both an adapter and
malformed diagnostics, should be treated as setup failures; the returned adapter
must not be used for rendering or execution.
Adapter setup failure cases must also verify that adapter-aware compile writes
no compiled SQL, marks affected compiled checks blocked with structured
diagnostics, de-duplicates repeated same-connection setup diagnostics in service
and CLI output, and preserves distinct source/target connection setup
diagnostics.

Adapter-aware compile tests should also cover the core-owned case where compile
validation fails before adapter rendering starts. When `--render-sql` was
requested, otherwise renderable checks must be marked `blocked` with
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, compiled SQL must not be
written, and adapter factories/renderers must not be invoked. A future shared
adapter test kit only needs this case when it drives core compile flows; pure
adapter API conformance should reference the core artifact requirement instead
of duplicating compiler validation tests.

The same adapter API conformance suite should cover profile rendering and
adapter diagnostic redaction before adapter execution, connection debug or
profile validation commands, external adapter repositories, or compatibility
claims rely on rendered profiles. It should verify selected profile/target
loading, referenced-connection filtering, missing environment variables,
environment-variable defaults, unsupported `{{ ... }}` template syntax, literal
adapter `type` handling, and adapter diagnostics returned after rendered
profile config is available. Literal adapter `type` cases should verify that
connection `type` is a non-empty literal string; `{{ ... }}` or `env_var(...)`
in `type` fails profile config before adapter resolution; adapter factories and
renderers are not invoked; compiled SQL is not written; and the rendered
environment value does not appear in diagnostics or artifacts. Adapter choices
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
Diagnostic `code` cases must include rendered values embedded without
separators, such as `RCsuper-secretLEAK` and `RC12LEAK`. Numeric field cases
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
- blocked checks include `blocked_by` and `skip_reason`,
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
