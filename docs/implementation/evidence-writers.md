# Evidence Writers

## Purpose

Evidence writers produce artifacts that explain what Recon checked, what assumptions were used, and what happened.

## Evidence writer responsibilities

Evidence writers should handle:

- terminal summaries,
- JSON run results,
- failure detail files,
- compiled artifact references,
- HTML reports,
- state references,
- sample key references.

## Writer boundaries

Check implementations should return structured data and artifact requests.

Evidence writers should handle file formats and paths.

Avoid writing files directly from deep check logic unless the check is explicitly producing a generated SQL file through the artifact layer.

## Failure detail writer

Failure detail output should support:

- CSV initially,
- JSONL later,
- row limits,
- optional disabling,
- masking/redaction hooks later.

Suggested path:

```text
target/failures/{contract_name}__{check_name}.csv
```

## HTML report writer

The HTML report should summarize:

- run status,
- contract status,
- check results,
- sampling scope,
- tolerances,
- null rules,
- schema ignores,
- CDC mode,
- declared grain keys,
- declared CDC keys,
- blocked checks and their prerequisites,
- failure links,
- warnings and errors.

A simple static HTML report is enough at first.

## Terminal summary writer

Terminal output should be concise and readable.

Example:

```text
Compiled 8 checks for 2 contracts
PASS customer_revenue.row_count_diff
FAIL customer_revenue.revenue_by_month
```

## Sensitive data handling

Evidence, failure details, reports, run results, terminal output, logs, adapter
runtime errors, and test snapshots may contain source/target values or private
source/target context.

Before execution, runner/results, or evidence/reporting surfaces are
implemented, Recon should define a source/target data privacy policy that
classifies raw rows, comparison keys, normalized values, aggregate values, row
counts, relation names, query text, runtime adapter errors, and database error
text as public, sensitive, or policy-controlled.

Initial protections:

- do not emit raw source/target rows by default,
- limit failure rows,
- allow failure detail export to be disabled,
- prefer summaries and artifact references over embedded values,
- sanitize runtime adapter and database errors before public output,
- clearly document generated evidence paths.

Future protections:

- masking,
- redaction,
- hash-only keys,
- sensitive column policies.

## Full versus sampled

Every report should show whether each check ran on:

- full data,
- deterministic sample,
- incremental window,
- persisted random sample,
- previous failure set.

Sampled evidence should not imply full-data equivalence.

Every report should also show whether key-dependent checks used `grain.keys` or
`cdc.keys`, and should identify any CDC behavior intentionally not validated.

## Design principle

Evidence should make Recon trustworthy by showing assumptions, scope, and generated behavior.
