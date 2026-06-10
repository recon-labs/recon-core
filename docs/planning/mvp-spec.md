# MVP Specification

## MVP goal

The MVP should prove that Recon can be a real Reconciliation as Code framework, not just a table diff script.

The first usable version should support a small but coherent workflow:

```text
define contract
parse project
compile explicit checks
run checks
produce evidence
```

The MVP should be strict, transparent, and extensible.

The MVP maps to the 0.1 release line, but completing implementation work does
not automatically bump or publish a package version. A 0.1 release requires a
separate release-readiness pass and explicit approval.

## MVP user story

A data engineer has source and target compare views. They want to prove that the target matches the source at a declared grain.

They create a Recon project, define an equivalence contract, run Recon from the CLI, inspect the compiled checks, and review evidence.

## Included scope

### CLI

Required commands:

```bash
recon --version
recon parse
recon compile
recon run
```

Recommended early command:

```bash
recon init
```

The first check-engine boundary for `recon run` consumes already compiled check
artifacts and fails clearly when those artifacts are missing, invalid, or empty.
Later runner phases may parse or compile automatically after artifact freshness
semantics are locked.

### Project config

Support:

```text
recon_project.yml
contracts/
sample_policies/
tolerances/
schema_policies/
target/
reports/
```

### Contracts

Support one contract per file first.

Support multiple contracts per file if the parser design is simple enough and does not delay the MVP.

Required contract fields:

- `version`,
- `name`,
- `source`,
- `target`,
- `checks`.

Required for row-level checks:

- `grain.keys`.

Required for CDC propagation checks:

- `cdc.keys`, or explicit `same_as: grain`.

Supported source/target definitions:

- `connection`,
- `relation`.

Query-based source/target should be designed in the schema and docs, but implementation can follow after relation-based execution is stable.

### Columns

Support explicitly declared columns.

Required rule:

> Recon must not silently compare all columns.

If no columns are defined, only checks that do not need columns can run.

### Metrics

Support explicit `sum` aggregate metrics.

Example:

```yaml
metrics:
  - name: total_revenue
    type: sum
    column: revenue
    tolerance: 0.01
```

Metrics compile into aggregate checks. Metric types beyond `sum` are post-MVP
work and should be added through an explicit aggregate metrics expansion
milestone.

### Checks

Required atomic checks:

- `row_count_diff`,
- `missing_keys`,
- `extra_keys`,
- `null_source_keys`,
- `null_target_keys`,
- `duplicate_source_keys`,
- `duplicate_target_keys`,
- `sum_diff`,
- basic explicit metric checks.

Recommended if feasible:

- `exact_value_match`,
- `numeric_tolerance_match`.

### Check packs

Required built-in check pack:

```text
recon_core.basic_equivalence
```

`recon_core.aggregate_equivalence` is deferred until its aggregate inference
behavior is explicitly designed. Explicit metrics are the initial aggregate
path.

CDC check pack can be documented and designed in MVP docs, but implementation can begin after basic and aggregate checks are stable.

### Sampling

Required modes:

- `full`,
- deterministic sample design.

Recommended implementation:

- preserve and validate authored sampling config for supported current behavior,
- show sampling scope in compiled artifacts and evidence,
- document numeric modulo and deterministic hash requirements, but do not execute
  those modes until the Post-MVP Milestone 24 sampling execution gate is
  resolved.

Persisted random, previous failures, incremental-watermark execution, and
sample-key state should be designed for future milestones. Their stateful
implementation belongs to v0.3 / Post-MVP Milestone 25.

### Tolerances

Required:

- numeric absolute tolerance at metric/check/column level.

Recommended:

- explicit null comparison default,
- `NULL != ''` unless configured through explicit string-like null sentinels,
- ordered string normalization steps with limited regex replacement,
- no relative, percentage, or timestamp tolerance execution in MVP.

### Schema policies

Required design:

- ignored target/source columns,
- ignored patterns,
- precision/scale compatibility as a schema concept.

Implementation can start with config parsing and simple column presence checks.

### Parse

`recon parse` should:

- read project files,
- validate YAML,
- validate basic schema,
- load contracts,
- detect duplicate contract names,
- validate referenced local resources where supported,
- write `target/manifest.json`.

### Compile

`recon compile` should:

- resolve defaults,
- expand check packs,
- compile metrics into checks,
- resolve sampling,
- resolve tolerance precedence,
- generate compiled contracts/checks,
- generate SQL/check queries where possible,
- write artifacts under `target/`.

Required compiled artifacts:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
```

Recommended compiled artifact:

```text
target/compiled_sql/
```

### Run

`recon run` should:

- parse and compile if needed,
- execute compiled checks,
- write run results,
- write failure details where configured,
- return non-zero on error-severity failures.

Required run artifact:

```text
target/run_results.json
```

Recommended report:

```text
reports/*.html
```

## Adapter scope

The MVP needs enough adapter support to prove the framework.

Recommended strategy:

- define the adapter interface in `recon-core`,
- define typed check plans before adapter SQL rendering,
- add adapter API versioning and capability declarations,
- implement one lightweight SQL adapter for local/dev testing,
- keep DuckDB as the first practical in-core local adapter path for repeatable
  development and tests,
- defer official production adapter packages until the adapter package/test-kit
  gates are satisfied. Experimental adapter work must not claim stable
  execution, sink, result-table, or probabilistic-summary compatibility before
  the relevant conformance gates exist and pass.

The MVP should avoid making `recon-core` depend on every database driver.

## Strict validation rules

The MVP must enforce these rules:

- no silent all-column comparison,
- row-level checks require `grain.keys`,
- CDC propagation checks require `cdc.keys`,
- row-level value and row-matching checks require non-null and unique source and
  target grain keys,
- row-level value checks are blocked by null or duplicate grain keys,
- `recon_core.basic_equivalence` requires `grain.keys`,
- metrics cause aggregate checks,
- columns do not cause checks by themselves,
- empty check-pack expansion is an error,
- check/column type incompatibility is an error,
- random sampling without persisted keys is invalid,
- hash sampling cannot assume cross-database equality,
- schema ignores must be explicit,
- CDC mode/delete behavior must be explicit for CDC checks.
- CDC delete validation can be explicitly disabled with `delete_mode: none`, but this must appear in artifacts and evidence.

## Out of MVP scope

The MVP should not include:

- cloud UI,
- hosted evidence vault,
- automatic data repair,
- full adapter ecosystem,
- MDM/fuzzy matching,
- complex package registry,
- full Recon Hub,
- advanced CDC operation semantics,
- SCD2 support,
- previous-failure state backend,
- persisted random sampling,
- `--select`, `--exclude`, `selectors.yml`, or partial compile/run execution,
- advanced permissions/secrets management.

The MVP run-result and evidence artifacts should still avoid assuming that
every future invocation is whole-project. They may reserve safe selected-scope
metadata or scope fields, but selector execution itself remains post-MVP.

## MVP example

```yaml
version: 1

name: customer_revenue

source:
  connection: legacy
  relation: qa.v_customer_revenue_compare

target:
  connection: warehouse
  relation: qa.v_customer_revenue_compare

grain:
  keys:
    - customer_id
    - month

columns:
  numeric:
    - name: revenue
      tolerance: 0.01

metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01

checks:
  use:
    - recon_core.basic_equivalence

sampling:
  default_policy: full

evidence:
  level: detailed
  store_failures: true
```

## MVP acceptance criteria

The MVP is acceptable when:

- contracts can be parsed and validated,
- check packs compile into explicit checks,
- metrics compile into aggregate checks,
- row-level checks block on null or duplicate keys,
- compiled artifacts are readable,
- run results are machine-readable,
- users can understand why each check passed, failed, warned, errored, or skipped,
- documentation matches implementation behavior.

After these criteria pass, Recon is eligible for a 0.1 release-readiness pass.
Post-MVP roadmap work belongs to the 0.2 line after the 0.1 release decision.
