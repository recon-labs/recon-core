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
file_path
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

### Parse errors

Invalid YAML, invalid shape, missing required fields, duplicate resource names.

### Compile errors

Invalid resolved behavior, unknown refs, unknown check packs, empty check-pack expansion, incompatible check/column types, missing policies.

### Validation errors

Unsafe or ambiguous behavior, such as row-level checks without keys or unsupported adapter capabilities.

### Runtime errors

Connection failures, query failures, adapter failures, metadata failures.

### Check failures

Checks ran successfully and found mismatches.

## Error messages

Errors should be clear and actionable.

Good:

```text
row_diff requires grain.keys because source and target rows must be matched.
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

Stable error codes should be introduced as behavior matures.

Example categories:

```text
RC_PARSE_*
RC_COMPILE_*
RC_VALIDATE_*
RC_ADAPTER_*
RC_RUNTIME_*
```

## CLI rendering

The CLI should print concise diagnostics.

Detailed diagnostics should be written to artifacts.

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
