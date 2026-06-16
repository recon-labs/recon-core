# Regression Capture

## Purpose

This directory records reusable regression and conformance memory for high-risk
Recon surfaces. It exists so fixed bugs, missed requirement details, and
future shared-conformance cases stay discoverable after individual tests are
renamed, moved, or split into other repositories.

Capture rows are not a replacement for tests. Each row points to current tests
that prove the behavior today, plus any future carryover gates that must be
rechecked when related milestone, adapter, package, artifact, CLI, or
automation work expands the same surface.

## What To Capture

Add or update a capture row when a change creates reusable conformance memory:

- a real regression found by review or user report,
- a missed high-risk or public-contract requirement,
- a bug class likely to recur when the same surface expands,
- a case that should later move into a shared adapter, package, or compatibility
  test suite.

Do not capture every unit test. Ordinary focused tests stay in normal test
files without capture metadata.

## Files

- `index.yml` defines carryover gates, status values, capture files, milestone
  anchors, and trigger surfaces.
- `adapter-runtime.yml` captures adapter runtime, scan-safety, capability, and
  cross-repo adapter cases.
- `check-engine.yml` captures check-engine semantics, blocker/dependency
  behavior, status/reason precedence, and execution-result cases.
- `diagnostics-privacy.yml` captures diagnostic rendering, redaction, and
  source/target privacy cases.
- `artifacts.yml` captures generated artifact publication, cleanup, freshness,
  and state/evidence artifact cases.
- `cli.yml` captures command, option, exit-code, terminal-output, selector, and
  debug-command behavior.
- `parser-compiler.yml` captures parser, compiler, contract YAML,
  check-pack, typed-plan, and validation-default behavior.

## Row Shape

Rows live under `captures` in the area file:

```yaml
captures:
  - id: duckdb-view-external-scan-guard
    title: Small DuckDB files with external-backed views do not prove bounded scans
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/services/test_run_service.py::test_run_service_blocks_key_safety_duckdb_view_over_external_file_before_adapter_setup
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
        expected_suite: scan_safety
    requirement_refs:
      - docs/compatibility/compatibility-matrix.md: Adapter test kit
    notes: >
      Core owns the allow/block decision. Future adapter conformance must prove
      truthful relation metadata or estimates; file size alone is not bounded
      scan evidence.
```

`id` values must be unique across every capture file. Keep notes short and
Recon-native. Do not include private review history or external research
attribution in public capture rows.

## Gate Statuses

Use the statuses defined in `index.yml`:

- `pending`: not yet resolved for the future surface.
- `covered`: current repo tests already satisfy the future surface's need.
- `migrated`: moved into a future shared suite, package, repository, or
  milestone test set.
- `deferred`: intentionally postponed with rationale.
- `not_applicable`: reviewed and determined irrelevant to that gate.

`deferred` and `not_applicable` require a rationale. `migrated` requires a
future test reference when the destination suite or repository exists.

## Discovery Rule

When implementing or reviewing milestone work:

1. Check `index.yml` for gates whose `primary_milestone` matches the capability
   being implemented.
2. If there is no direct match, check `applies_to`.
3. If the work is new, renamed, or not listed, match touched files and public
   surfaces to `trigger_surfaces`.
4. Review matching capture rows before calling the milestone complete.

If an applicable row is still `pending`, the work is not complete until that row
is marked `covered`, `migrated`, `deferred`, or `not_applicable` with the
required rationale or references.
