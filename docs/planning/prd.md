# Product Requirements

## Product summary

Recon is an open-source Reconciliation as Code framework for proving data equivalence across CDC pipelines, warehouse migrations, pipeline refactors, medallion layers, and business logic rewrites.

Recon lets teams define source-target equivalence in code, run repeatable checks, and generate evidence that can be used for debugging, CI, orchestration, and sign-off.

## Problem

Data teams often need to prove that one dataset matches another:

- operational source table versus warehouse replica,
- MongoDB collection versus BigQuery table,
- SQL Server source versus Snowflake target after DMS/Snowpipe,
- old Redshift/Spark output versus new Snowflake output,
- old pipeline result versus refactored pipeline result,
- Bronze versus Silver versus Gold layer,
- old business metric versus new business metric.

Today this work is often done with ad hoc SQL, spreadsheets, screenshots, analyst QA, Slack threads, and tickets. The logic is not consistently versioned, reruns are manual, and evidence is scattered.

Recon turns this into a structured engineering workflow.

## Target users

Primary users:

- data engineers,
- analytics engineers,
- data platform engineers,
- migration engineers,
- senior analysts who validate business outputs.

Secondary users:

- data quality engineers,
- data architects,
- data governance teams,
- engineering managers,
- business stakeholders reviewing evidence.

## Core use cases

### Continuous CDC validation

Validate that source data replicated into a warehouse remains complete, fresh, and equivalent.

Examples:

- SQL Server to Snowflake through AWS DMS and Snowpipe,
- MongoDB to BigQuery,
- Postgres to a warehouse through Debezium/Kafka.

### Migration and parallel-run validation

Validate old output versus new output before cutover.

Examples:

- Redshift to Snowflake,
- Spark pipelines rewritten as dbt or Snowpark,
- legacy reporting mart replaced by a governed warehouse model.

### Pipeline refactor validation

Validate that a rewritten pipeline produces equivalent output.

Examples:

- Spark job rewritten as SQL,
- Python transform replaced by dbt model,
- legacy Airflow task replaced by modern framework code.

### Medallion layer reconciliation

Validate expected behavior across Bronze, Silver, and Gold layers.

Examples:

- Bronze matches source,
- Silver preserves key coverage,
- Gold aggregates reconcile to Silver.

### Business logic equivalence

Validate old and new business calculations.

Examples:

- old revenue logic versus new revenue logic,
- old churn feature output versus new feature output,
- legacy dashboard table versus governed semantic table.

## Product goals

Recon should:

- make reconciliation logic versioned and reviewable,
- define source-target equivalence through contracts,
- support relation-first comparison and custom query comparison,
- support reusable checks and check packs,
- support reusable sampling, tolerance, schema, and evidence policies,
- generate human-readable and machine-readable artifacts,
- work from CLI and fit CI/orchestration workflows,
- be adapter-based and ecosystem-friendly,
- avoid hidden behavior and unsafe assumptions.

## Non-goals

Recon is not:

- a generic data quality platform,
- an ingestion or CDC movement tool,
- a dbt replacement,
- a dashboarding product first,
- an MDM or fuzzy entity resolution platform,
- an automatic data repair tool,
- a cloud-first product before the open-source framework is useful.

## Product principles

### Source-target equivalence is the core

Recon exists to answer:

> Does this target output match the source, old output, replicated system, or expected business output according to a defined contract?

### Contracts are the public language

The equivalence contract is the main user-authored object.

Contracts define source, target, grain, keys, columns, metrics, checks, sampling, tolerances, schema behavior, CDC behavior, evidence, severity, tags, and ownership.

Contracts distinguish comparison identity (`grain.keys`) from CDC identity
(`cdc.keys`).

### Explicit beats surprising

Recon should not silently compare all columns, silently skip empty check packs, silently coerce incompatible types, or silently guess mappings.

### Evidence is part of the product

Every run should produce enough evidence to understand what was checked, what passed, what failed, what was sampled, what was ignored, and what assumptions were used.

### Compile hidden behavior into visible artifacts

Defaults, refs, check packs, metrics, sampling policies, tolerance policies, schema policies, and CDC policies should compile into explicit generated artifacts.

### Adapter-based by design

Core should define framework behavior and interfaces. System-specific behavior belongs in adapters.

## Core workflow

```text
authored project files
  -> recon parse
  -> recon compile
  -> recon run
  -> results and evidence
```

### Parse

`recon parse` validates project structure and produces a machine-oriented manifest.

### Compile

`recon compile` resolves defaults, refs, check packs, metrics, sampling, tolerances, schema policies, and CDC settings into human-readable execution artifacts and SQL/check queries.

### Run

`recon run` executes checks and produces results and evidence.

## User experience requirements

Recon should feel:

- CLI-first,
- Git-friendly,
- readable,
- deterministic,
- debuggable,
- safe by default,
- easy to run locally,
- easy to schedule in Airflow or CI later.

## Functional requirements

### Project initialization

Recon should provide a `recon init` command that creates a starter project.

Expected structure includes:

- `recon_project.yml`,
- `connections/profiles.yml.example`,
- `contracts/`,
- `check_packs/`,
- `macros/`,
- `sample_policies/`,
- `tolerances/`,
- `schema_policies/`.

### Contract loading

Recon should support:

- one contract per file,
- multiple contracts per file,
- shared defaults,
- reusable references later,
- validation of duplicate contract names.

### Source and target definitions

Recon should support:

- relation-based source/target,
- query-based source/target,
- existing compare views,
- canonical outputs for surrogate-key differences,
- future reusable endpoint refs.

### Check execution

Recon should support:

- row count,
- missing keys,
- extra keys,
- null keys,
- duplicate keys,
- aggregate checks,
- row-level value checks,
- schema checks,
- CDC checks.

### Sampling

Recon should support:

- full data,
- deterministic hash or numeric modulo,
- incremental window,
- persisted random later,
- previous failures later,
- per-check sampling overrides.

### Tolerances and normalization

Recon should support:

- numeric absolute tolerance,
- timestamp tolerance later,
- null/empty-string rules,
- string normalization later,
- project/contract/column/check-level override precedence.

### Schema policies

Recon should support:

- column presence checks,
- type compatibility,
- precision/scale compatibility,
- ignored source/target columns,
- ignored column patterns,
- CDC technical column handling.

### CDC behavior

Recon should support explicit CDC modes:

- snapshot comparison,
- upsert CDC,
- append-only event CDC,
- timestamp-window CDC,
- batch/load-id CDC,
- explicit CDC keys for propagation checks,
- hard delete,
- soft delete,
- operation-column delete,
- tombstone delete later,
- SCD2-style history later.

### Evidence

Recon should produce:

- terminal summary,
- `target/manifest.json`,
- compiled contracts/checks/SQL,
- `target/run_results.json`,
- failure details,
- HTML reports,
- sample keys when needed.

## Quality requirements

Recon should be:

- tested with TDD for non-trivial logic,
- strict in validation,
- clear in errors and warnings,
- stable in public YAML design,
- easy to extend through adapters and packages,
- friendly to contributors.

## Success criteria

A successful first release should let a user:

1. initialize or manually create a Recon project,
2. define at least one equivalence contract,
3. run basic source-target checks,
4. compare explicit numeric metrics with tolerance,
5. generate a run result and readable evidence,
6. inspect compiled checks and SQL,
7. understand every warning or error without reading framework code.
