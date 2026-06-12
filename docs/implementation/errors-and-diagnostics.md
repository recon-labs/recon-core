# Errors and Diagnostics

## Purpose

Diagnostics provide structured errors and warnings across parse, compile, run, and evidence.

Validation timing and diagnostic code ownership are locked by
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

## Diagnostic model

Suggested model:

```python
@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    resource_type: str | None = None
    resource_name: str | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None
    hint: str | None = None
```

## Severity

Diagnostic severities:

```text
info
warning
error
```

Check statuses are separate:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

`unsupported` and `not_yet_executable` are not check statuses. They are
machine-readable reason-code concepts for `not_executable` check results.

## Error code categories

Recommended categories:

```text
RC_CONFIG_*
RC_PARSE_*
RC_COMPILE_*
RC_VALIDATE_*
RC_ADAPTER_*
RC_RUNTIME_*
RC_EVIDENCE_*
```

Code ownership:

| Family | Primary owner | Use for |
| --- | --- | --- |
| `RC_CONFIG_*` | configuration phase | project discovery, project config, future profiles, env vars, command setup |
| `RC_PARSE_*` | parse phase | authored-file discovery, YAML loading, structural resource validation |
| `RC_COMPILE_*` | compile resolution | expansion, resolution, unsupported compiler input, generated compiled structure |
| `RC_VALIDATE_*` | validation rules | semantic safety rules and public validation behavior, usually during compile |
| `RC_ADAPTER_*` | adapter phase | adapter type, API compatibility, capabilities, metadata, rendering, query execution |
| `RC_RUNTIME_*` | run phase | run lifecycle, prerequisite blocking, state/failure-detail writes |
| `RC_EVIDENCE_*` | evidence phase | evidence/report rendering, redaction, evidence artifact writes |

Do not add codes from a new family unless that phase owns the failure.

## Validation timing

| Timing | Should validate | Should not validate |
| --- | --- | --- |
| Configuration | project root, `recon_project.yml`, supported config fields, future profile/env-var shape | authored contract semantics, check expansion, adapter metadata |
| Parse | file reads, duplicate-safe YAML, structural contract shape, loaded-resource duplicate names | check-pack expansion, metric compilation, sampling/tolerance precedence, adapter capabilities |
| Compile resolution | defaults/refs, supported check-pack invocation shape, check-pack expansion, explicit metrics, stable IDs, no contracts/checks | query execution, data-dependent key uniqueness/null checks |
| Compile validation | missing required keys, invalid semantic combinations, unsupported current behavior, malformed sampling/CDC/schema policy config once supported | adapter metadata facts that are unavailable without an adapter |
| Adapter validation | adapter type/API/capabilities, metadata availability, metadata-derived column/type checks | core reconciliation semantics |
| Run | compiled artifact loading, adapter execution, data-dependent safety checks, prerequisite blocking | raw authored YAML interpretation |
| Evidence | evidence/report/failure-detail output and redaction | validation rules that should have failed before execution |

Deferred validation is allowed only when the required information is unavailable
in the current phase, such as adapter metadata or execution results. Deferred
validation must be visible in generated artifacts or run results before users
trust evidence. Unknown fields, unsupported check-pack config, missing keys,
and ambiguous CDC behavior should fail rather than defer.

## Parse diagnostics

Examples:

```text
RC_PARSE_FILE_READ_ERROR
RC_PARSE_INVALID_YAML
RC_PARSE_INVALID_CONTRACT
RC_PARSE_MISSING_REQUIRED_FIELD
RC_PARSE_DUPLICATE_CONTRACT
RC_PARSE_INVALID_ENDPOINT
RC_PARSE_RESOURCE_PATH_NOT_FOUND
RC_PARSE_AMBIGUOUS_RESOURCE_FILE
RC_PARSE_UNKNOWN_FIELD
```

Resource loading diagnostics locked by ADR 0017:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_PARSE_RESOURCE_PATH_NOT_FOUND` | parse | error |
| `RC_PARSE_AMBIGUOUS_RESOURCE_FILE` | parse | error |
| `RC_PARSE_DUPLICATE_RESOURCE_NAME` | parse | error |

Source-file indexing should use
`RC_PARSE_RESOURCE_PATH_NOT_FOUND` for missing or non-directory required paths
and explicitly configured optional paths. It should use
`RC_PARSE_AMBIGUOUS_RESOURCE_FILE` when one source file is reachable through
multiple resource kinds. `RC_PARSE_DUPLICATE_RESOURCE_NAME` should be used only
after a resource kind has a parsed, named resource model; index-only files do
not have resource names.

Check-pack resource schema diagnostics locked by ADR 0018:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_PARSE_INVALID_CHECK_PACK_CONFIG_SCHEMA` | parse | error |

Invalid authored YAML diagnostics are public output. Low-level YAML parser
errors often quote the offending line or nearby snippet, and contract files can
contain source/target query text or private literals. `RC_PARSE_INVALID_YAML`
messages should therefore use safe summaries such as `Invalid YAML in resource
file.` instead of raw parser exception text. Known structural cases may use
safe category-specific messages, such as duplicate-key or unsupported-mapping
summaries, but they must not echo authored key values or source/target
snippets. Tests should assert that terminal output and manifest diagnostics do
not expose offending query text, row-like values, credentials, or other private
literals from malformed contract or resource files.

## Configuration diagnostics

Examples:

```text
RC_CONFIG_PROJECT_NOT_FOUND
RC_CONFIG_INVALID_PROJECT_YAML
RC_CONFIG_INVALID_PROJECT_CONFIG
RC_CONFIG_INIT_PATH_EXISTS
RC_CONFIG_INIT_INVALID_PROJECT_NAME
```

Future package/resource namespace diagnostics locked by ADR 0017:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_CONFIG_RESERVED_RESOURCE_NAMESPACE` | config | error |
| `RC_CONFIG_DUPLICATE_PACKAGE_NAMESPACE` | config | error |
| `RC_CONFIG_PACKAGE_NOT_INSTALLED` | config | error |

Configuration YAML diagnostics follow the same sanitization rule as parse
diagnostics. `RC_CONFIG_INVALID_PROJECT_YAML` and future profile/package config
YAML diagnostics must not directly use raw YAML parser exception text when the
exception can quote authored snippets, rendered profile values, credentials, or
private project details. Use safe summary messages and preserve the diagnostic
code, severity, path, and safe hint instead.

## Compile diagnostics

Examples:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_COMPILE_UNSUPPORTED_CHECK_PACK_CONFIG
RC_COMPILE_UNSUPPORTED_EXPLICIT_CHECKS
RC_COMPILE_UNKNOWN_SAMPLE_POLICY
RC_COMPILE_UNKNOWN_TOLERANCE_POLICY
RC_COMPILE_UNKNOWN_SCHEMA_POLICY
RC_COMPILE_UNKNOWN_ENDPOINT
RC_COMPILE_EMPTY_CHECK_PACK_ALLOWED
RC_COMPILE_EMPTY_CHECK_PACK_SKIPPED
```

Unknown macro-reference diagnostics are not locked yet. Macro reference
validation requires a future macro-semantics decision.

Check-pack invocation diagnostics locked by ADR 0018:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_COMPILE_UNSUPPORTED_CHECK_PACK_CONFIG` | compile resolution | error |
| `RC_COMPILE_EMPTY_CHECK_PACK` | compile resolution | error |
| `RC_COMPILE_EMPTY_CHECK_PACK_ALLOWED` | compile resolution | warning |
| `RC_COMPILE_EMPTY_CHECK_PACK_SKIPPED` | compile resolution | info |

## Validation diagnostics

Examples:

```text
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_DUPLICATE_KEYS_BLOCK_ROW_CHECK
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION
RC_VALIDATE_INVALID_STABLE_ID_PART
RC_VALIDATE_INVALID_SAMPLING
RC_VALIDATE_NO_CONTRACTS_FOUND
RC_VALIDATE_NO_COMPILED_CHECKS
RC_VALIDATE_INVALID_METRIC
RC_VALIDATE_UNKNOWN_METRIC_FIELD
RC_VALIDATE_UNSUPPORTED_METRIC_TYPE
RC_VALIDATE_DUPLICATE_METRIC_NAME
RC_VALIDATE_INVALID_COLUMN_DECLARATION
RC_VALIDATE_DUPLICATE_COLUMN_NAME
RC_VALIDATE_UNDECLARED_COLUMN_REFERENCE
RC_VALIDATE_INVALID_COLUMN_SELECTION
RC_VALIDATE_COLUMN_NOT_ELIGIBLE_FOR_CHECK
RC_VALIDATE_ALL_COLUMNS_REQUIRES_METADATA
RC_VALIDATE_RANDOM_SAMPLE_REQUIRES_PERSISTED_KEYS
RC_VALIDATE_INVALID_CDC_KEYS
RC_VALIDATE_CDC_CONFIG_REQUIRED
RC_VALIDATE_CDC_DELETE_MODE_REQUIRED
RC_VALIDATE_CDC_ORDERING_REQUIRED
RC_VALIDATE_SCHEMA_IGNORE_INVALID
RC_VALIDATE_INVALID_TOLERANCE
RC_VALIDATE_INVALID_NULL_POLICY
RC_VALIDATE_INVALID_NULL_SENTINEL
RC_VALIDATE_INVALID_NORMALIZATION
RC_VALIDATE_INVALID_REGEX_NORMALIZATION
RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED
```

The validation rulebook should use these locked diagnostics:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS` | compile validation | error |
| `RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS` | compile validation | error |
| `RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS` | compile validation | error |
| `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` | compile or adapter metadata validation | error |
| `RC_VALIDATE_INVALID_COLUMN_DECLARATION` | compile validation | error |
| `RC_VALIDATE_DUPLICATE_COLUMN_NAME` | compile validation | error |
| `RC_VALIDATE_UNDECLARED_COLUMN_REFERENCE` | compile validation | error |
| `RC_VALIDATE_INVALID_COLUMN_SELECTION` | compile validation | error |
| `RC_VALIDATE_COLUMN_NOT_ELIGIBLE_FOR_CHECK` | compile validation | error |
| `RC_VALIDATE_ALL_COLUMNS_REQUIRES_METADATA` | adapter metadata validation | error |
| `RC_VALIDATE_INVALID_SAMPLING` | compile validation | error |
| `RC_VALIDATE_RANDOM_SAMPLE_REQUIRES_PERSISTED_KEYS` | compile validation | error |
| `RC_VALIDATE_INVALID_CDC_KEYS` | compile validation | error |
| `RC_VALIDATE_CDC_CONFIG_REQUIRED` | compile validation | error |
| `RC_VALIDATE_CDC_DELETE_MODE_REQUIRED` | compile validation | error |
| `RC_VALIDATE_CDC_ORDERING_REQUIRED` | compile validation | error |
| `RC_VALIDATE_SCHEMA_IGNORE_INVALID` | compile validation | error |
| `RC_VALIDATE_INVALID_TOLERANCE` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_POLICY` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_SENTINEL` | compile validation | error |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_INVALID_REGEX_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error |
| `RC_VALIDATE_METADATA_VALIDATION_DEFERRED` | adapter metadata validation | warning |
| `RC_VALIDATE_UNUSED_DECLARED_COLUMN` | compile validation | warning |

Additional check-pack invocation validation diagnostics locked by ADR 0018:

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_VALIDATE_DUPLICATE_CHECK_PACK_INVOCATION` | compile validation | error |
| `RC_VALIDATE_INVALID_CHECK_PACK_ON_EMPTY` | compile validation | error |
| `RC_VALIDATE_INVALID_CHECK_PACK_CONFIG` | compile validation | error |
| `RC_VALIDATE_UNKNOWN_CHECK_PACK_CONFIG_KEY` | compile validation | error |
| `RC_VALIDATE_UNUSED_CHECK_PACK_CONFIG` | compile validation | error |

Data-dependent null-key and duplicate-key problems are runtime check results,
not compile-time validation diagnostics. They should fail the corresponding
safety check and block dependent row-level value checks.

## Adapter diagnostics

Examples:

```text
RC_ADAPTER_UNKNOWN_TYPE
RC_ADAPTER_RESOLUTION_FAILED
RC_ADAPTER_API_VERSION_UNSUPPORTED
RC_ADAPTER_CAPABILITY_UNSUPPORTED
RC_ADAPTER_CAPABILITY_DECLARATION_FAILED
RC_ADAPTER_DEPENDENCY_MISSING
RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED
RC_ADAPTER_TYPE_MISMATCH
RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED
RC_ADAPTER_INVALID_RELATION
RC_ADAPTER_OPERATION_RENDER_FAILED
RC_ADAPTER_RENDERED_SQL_EMPTY
RC_ADAPTER_RENDERER_METADATA_INVALID
RC_ADAPTER_RENDERER_TYPE_MISMATCH
RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED
RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS
RC_ADAPTER_METADATA_INVALID
RC_ADAPTER_CONNECTION_FAILED
RC_ADAPTER_CLOSE_FAILED
RC_ADAPTER_QUERY_FAILED
```

Adapter-aware compile uses `RC_ADAPTER_*` diagnostics for adapter
type resolution, empty or malformed adapter factory results, malformed factory
diagnostic payloads, adapter factory exceptions, adapter API compatibility,
missing or invalid adapter API version declarations, capability declaration
failures, malformed capability support states, required-capability validation,
optional dependency checks,
relation-only rendering boundaries, same-context rendering requirements,
profile `type`/adapter metadata mismatches, invalid relation names, invalid
adapter metadata, renderer metadata mismatches, renderer failures, empty
renderer output, malformed non-empty renderer output, and invocation-wide SQL
output suppression. Exported rendering helpers that accept an explicit renderer
must validate renderer `adapter_type` before invoking `render_plan()`, surfacing
`RC_ADAPTER_RENDERER_METADATA_INVALID` for missing, empty, non-string, or
exception-raising renderer metadata and
`RC_ADAPTER_RENDERER_TYPE_MISMATCH` for a renderer that does not match the
resolved adapter type. When
`recon compile --render-sql` cannot start adapter rendering because compile
validation already failed, otherwise renderable checks should use
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` in compiled checks
artifacts so generated metadata does not imply that rendering was not requested.
Service-level diagnostics should de-duplicate identical contract or endpoint
rendering blockers that affect multiple checks, while compiled-check diagnostics
should still explain each blocked check. These diagnostics must not include
connection secrets or fully rendered credential payloads. If an adapter setup
failure and an independent render failure occur in the same
adapter-aware compile invocation, service and CLI diagnostics must preserve both
distinct failures; setup diagnostics must not mask render diagnostics from
otherwise resolvable contracts.
If a profile-backed adapter diagnostic, including factory diagnostics, adapter
API compatibility diagnostics, and render-phase adapter diagnostics, references
rendered connection config keys or values, Recon should suppress unsafe adapter
diagnostic text and unsafe resource metadata, then return a generic adapter
diagnostic with the original severity and the original diagnostic code only when
the code is safe. If an adapter-provided diagnostic code references rendered
connection config keys or values, Recon should replace it with
`RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`. The replacement diagnostic must still
include a safe, actionable message and safe resource context. Diagnostic-code
redaction must include unsafe config keys and rendered values in both
delimiter-separated and separatorless forms. Examples such as
`RC_PASSWORD_LEAK` and `RCPASSWORDLEAK` must be treated as unsafe when
`password` is an unsafe rendered connection config key, and examples such as
`RCsuper-secretLEAK` and `RC12LEAK` must be treated as unsafe when
`super-secret` or `12` came from rendered profile config. Rendered profile
values include scalar YAML values after rendering, including non-string values
such as numeric credentials and rendered numeric strings such as quoted YAML or
env-var-derived `"12.0"`.
If an adapter factory returns a malformed result, or if an adapter factory,
adapter metadata declaration, or capability declaration raises an exception,
Recon should suppress raw adapter payloads and return a generic structured
adapter diagnostic that preserves only the exception type when useful.
Suppression should treat case-changed keys or rendered values, DSN fragments,
tokens, passwords, numeric formatting changes, and other simple transformations
as unsafe when they can be derived from rendered profile config. Redaction tests
should cover every public diagnostic field independently: `code`, `message`,
`hint`, `path`, `resource_type`, `resource_name`, `line`, `column`,
`rendering.adapter_type`, and any future structured diagnostic fields.

Adapter diagnostics are part of the adapter compatibility surface. Future
adapter execution, debug/profile validation commands, external adapter
packages, and shared adapter test-kit conformance must require adapter-provided
diagnostics to include safe non-empty messages. Those messages must explain the
failure without exposing credentials, tokens, DSNs, rendered connection
payloads, or other secret-classified values in any public diagnostic field,
including diagnostic `code`.
Shared adapter test-kit redaction cases must include numeric `line` and
`column` fields when those values match rendered scalar profile values, not only
string diagnostic text. These cases must also include unsafe config keys and
rendered values embedded inside diagnostic `code` without separators, such as
`RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`, plus delimiter-separated
key-token cases such as `RC_PASSWORD_LEAK`. Short numeric rendered scalars such
as port values must be covered when they appear in diagnostic `code`, `message`,
`hint`, `path`,
`resource_type`, `resource_name`, numeric `line`/`column`, and
`rendering.adapter_type`. Short numeric cases must include equivalent formatted
variants such as `12`, `12.0`, `+12`, and integer-equivalent scientific
notation, because adapters may stringify the same rendered scalar differently.
They must cover rendered numeric strings such as `"12.0"` as profile values, not
only adapter diagnostics that emit decimal text from integer profile values.
Long password-shaped numeric values alone do not prove exact short-token
redaction. Core compile-flow conformance must also verify
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` appears in compiled-check
metadata when compile validation prevents a requested adapter rendering phase
from starting.

## Runtime diagnostics

First check-engine result diagnostics use the runtime family because they are
created while loading compiled check artifacts or preparing run-time check
results. Locked codes:

| Code | Timing | Severity | Use for |
| --- | --- | --- | --- |
| `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND` | run | error | Expected compiled-check artifacts are missing. |
| `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID` | run | error | A compiled-check artifact is unreadable, malformed, unsafe to load, or incompatible with the current loader. |
| `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND` | run | error | A compiled check references a compiled-contract artifact that cannot be found. |
| `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID` | run | error | A compiled-contract artifact is unreadable, malformed, unsafe to load, incompatible with the current loader, or mismatched with the compiled-check reference. |
| `RC_RUNTIME_NO_COMPILED_CHECKS` | run | error | No compiled checks are available in the requested run scope. This must not be reported as `pass`. |
| `RC_RUNTIME_CHECK_NOT_EXECUTABLE` | run | error | A compiled check is valid but cannot execute in the current check-engine surface. |
| `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE` | run | error | The compiled check type has no internal dispatch handler. |
| `RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION` | run | error | The compiled typed operation has no runtime executor in the current check-engine surface. |
| `RC_RUNTIME_MISSING_ENGINE_CAPABILITY` | run | error | A compiled check requires an engine capability that is unavailable in the current check-engine boundary. |
| `RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT` | run | error | Required operation or comparison placement is not implemented or allowed. |
| `RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY` | run | error | Required staging, movement, or materialization policy is not implemented or allowed. |
| `RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE` | run | error | A check did not run because a prerequisite failed, errored, was not executable, or is missing. |
| `RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR` | run | error | An unexpected check-engine error occurred after sanitization. |

Runtime adapter execution adds adapter-family diagnostics for connection,
execution, and close failures. `RC_ADAPTER_CONNECTION_FAILED`,
`RC_ADAPTER_QUERY_FAILED`, and `RC_ADAPTER_CLOSE_FAILED` must preserve safe
machine context and actionable messages while suppressing raw SQL, rendered
SQL, database engine error text, rendered profile values, credentials, DSN
fragments, tracebacks, relation data, and source/target values. Close failures
must not hide a primary execution failure.

Future runtime, state, evidence, and key-safety phases may add or retain
additional runtime-family codes for check execution errors, key safety failures,
artifact writes, state writes, and evidence writes when those behaviors are
implemented. Those later-phase codes are not part of the first check-engine
boundary until their owning phase locks semantics, compatibility docs, and test
coverage.

These diagnostics explain non-execution; they are not reconciliation mismatch
evidence. They must preserve safe code, severity, message, resource context,
path, and hint where available. They must not expose raw source/target values,
query text, relation names, rendered profile values, credentials, raw database
errors, raw tracebacks, or unredacted artifact contents.

## Message style

Messages should be direct and actionable.

Good:

```text
row_diff requires grain.keys because source and target rows must be matched.
```

Bad:

```text
invalid contract
```

## Output conformance

Diagnostic output should preserve both the machine code and the human message.
The minimum diagnostic fields for public output are:

```text
code
severity
message
```

This applies to terminal output, manifest diagnostics, compiled-check
diagnostics, future run results, evidence/report output, debug/profile
validation commands, and adapter test-kit assertions. Path, resource context,
line, column, and hint should be preserved when available.

Tests should treat missing diagnostic messages as a public-output regression,
even when the diagnostic code is present. Redaction may replace unsafe message
text with a generic safe message, but it must not leave users with only a code
or hint.

Runtime diagnostics and adapter/database error diagnostics must also follow the
source/target data privacy policy before check execution, runner/results,
evidence/reporting, debug commands, or adapter test-kit surfaces expose source
or target data. Raw rows, comparison keys, normalized values, aggregate values,
row counts, relation names, query text, and database error text must not leak
through diagnostic `message`, `hint`, `path`, resource metadata, line/column
fields, terminal output, run results, evidence, reports, logs, or test snapshots
unless the policy explicitly allows that output.

For the check-engine split, the first check-engine boundary owns diagnostics
that do not require adapter execution. Row-count execution owns runtime adapter
diagnostics, grain-key safety execution owns key-safety diagnostics, and
aggregate execution owns aggregate diagnostics. Run-result diagnostics and
evidence/report/failure-detail diagnostics remain separate later surfaces unless
a later split explicitly changes those boundaries.

Do not pass raw low-level exception strings directly into public diagnostics
when those exceptions can contain authored YAML snippets, rendered connection
values, source/target query text, relation names, row values, or database error
payloads. This includes YAML parser errors, adapter factory errors, adapter
metadata/capability errors, database client errors, runtime execution errors,
and future evidence writer errors. Public diagnostics should summarize the
failure with safe text and keep useful machine context through the diagnostic
code, severity, path, resource fields, and safe hints.

## Hints

Hints should help users fix the issue.

Example:

```text
Add grain.keys or remove row-level value checks from this contract.
```

Example:

```text
Declare cdc.keys for delete_propagation or remove CDC propagation checks from this contract.
```

## Artifact inclusion

Diagnostics should appear in:

```text
target/manifest.json
target/compiled_checks/
target/run_results.json
reports/
```

## Design principle

Diagnostics should make Recon safe to use without reading the source code.
