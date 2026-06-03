# Diagnostics and Errors

## Diagnostic model

Recon should use structured diagnostics for errors and warnings.

A diagnostic should include:

```text
code
severity
message
resource_type
resource_name
path
line
column
hint
```

Line and column may be unavailable for some diagnostics, but file and resource context should be included when possible.

## Severity levels

Recommended severities:

```text
info
warning
error
```

Runtime check statuses are separate:

```text
pass
fail
warn
error
skipped
```

## Error categories

### Configuration diagnostics

Project discovery, project config loading, future profile loading, environment
variable resolution, and command setup failures.

Code family:

```text
RC_CONFIG_*
```

Configuration errors prevent parse, compile, or run from continuing because
Recon does not have safe project context.

### Parse diagnostics

Invalid YAML, invalid shape, missing required fields, duplicate resource names.

Parse diagnostics are structural and authored-file oriented. Parse should not
expand check packs, compile metrics, resolve policies, validate adapter
capabilities, or execute queries.

Code family:

```text
RC_PARSE_*
```

### Compile and validation diagnostics

Invalid resolved behavior, unknown refs, unknown check packs, empty check-pack expansion, incompatible check/column types, missing policies.

Unsafe or ambiguous behavior, such as row-level checks without keys, CDC
propagation checks without CDC keys, CDC checks without required delete mode or
ordering, or unsupported adapter capabilities.

Use `RC_COMPILE_*` for compiler resolution, expansion, unsupported compiler
input, or generated-structure problems.

Use `RC_VALIDATE_*` for semantic safety rules or public validation rules, even
when those rules execute during `recon compile`.

Compile may write diagnostic-bearing compiled artifacts when they are safe and
useful for inspection, but error diagnostics prevent run.

### Adapter diagnostics

Adapter type resolution, adapter API compatibility, declared capabilities,
metadata availability, metadata-derived validation, SQL rendering support, and
query execution.

Code family:

```text
RC_ADAPTER_*
```

Unsupported capabilities should fail before run when known. Metadata-dependent
validation may be deferred only when generated artifacts or run results visibly
record the deferred condition.

### Runtime diagnostics

Connection failures, query failures, adapter failures, metadata failures.

Runtime diagnostics also include run lifecycle failures, state writes, failure
detail writes, and prerequisite blocking.

Code family:

```text
RC_RUNTIME_*
```

### Check failures

Checks ran successfully and found mismatches.

Check failures are not validation diagnostics. For example, null-key and
duplicate-key checks fail after reading source or target data, and dependent
row-level checks should be skipped with explicit `blocked_by` and
`skip_reason`.

### Evidence diagnostics

Evidence writer, report writer, redaction, failure-detail, and evidence
artifact failures.

Code family:

```text
RC_EVIDENCE_*
```

## Error messages

Errors should be clear and actionable.

Good:

```text
row_diff requires grain.keys because source and target rows must be matched.
```

```text
delete_propagation requires cdc.keys because CDC delete validation needs change identity.
```

Bad:

```text
invalid contract
```

## Warning messages

Warnings should identify suspicious but allowed behavior.

Example:

```text
Column revenue is defined but not used by any compiled check.
```

## Error codes

Diagnostic codes are public enough for users and automation to rely on during
pre-1.0 development. Do not reuse a code for a different meaning, and do not
rename codes without compatibility review.

Example categories:

```text
RC_CONFIG_*
RC_PARSE_*
RC_COMPILE_*
RC_VALIDATE_*
RC_ADAPTER_*
RC_RUNTIME_*
RC_EVIDENCE_*
```

Milestone 5 validation timing and diagnostic code ownership are locked in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

## CLI rendering

The CLI should print concise diagnostics. Failed commands should include each
diagnostic code and message, plus path and hint when available.

Detailed diagnostics should be written to artifacts.

## Diagnostic output conformance

Diagnostic messages are part of Recon's public diagnostic contract, not
optional terminal decoration. Any user-facing or automation-facing diagnostic
surface should preserve at least:

```text
code
message
severity
```

When available, diagnostic output should also preserve path, resource context,
and hint. CLI, manifest, compiled artifact, run result, evidence, report, debug
command, and future adapter test-kit views may format diagnostics differently,
but they must not rely on code or hint alone when an actionable message exists.

Redaction must happen before diagnostics are rendered or written. Secret-safe
rendering should remove credentials, tokens, DSNs, rendered connection payloads,
and other secret-classified values from diagnostic message, hint, path,
`resource_type`, `resource_name`, and future structured diagnostic fields
without dropping the diagnostic message entirely. If a message or resource
field cannot be made safe, Recon should replace it with generic safe text while
preserving the original code, severity, and non-secret context.

## Artifact rendering

Diagnostics should be included in:

```text
target/manifest.json
target/compiled_checks/
target/run_results.json
reports/
```

## Design principle

Users should understand what failed, where it failed, why it failed, and how to fix it.
