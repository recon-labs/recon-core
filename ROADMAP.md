# Roadmap

Recon Core is being built as an open-source Reconciliation as Code framework.

The roadmap prioritizes a small trustworthy core before broad adapter and package expansion.

## Near-term goals

### Core framework loop

Build the first complete workflow:

```text
contract -> parse -> compile -> run -> evidence
```

This includes:

- project configuration,
- contract parsing,
- manifest generation,
- check-pack expansion,
- metric compilation,
- typed check plans,
- adapter capability validation,
- validation diagnostics,
- compiled artifacts,
- adapter-rendered SQL,
- check execution,
- run results,
- evidence output.

### Strict validation

Protect users from misleading evidence.

Important rules:

- no silent all-column comparison,
- no silent no-op check packs,
- row-level checks require unique keys,
- sampling does not remove uniqueness requirements,
- schema ignores are explicit,
- CDC behavior is explicit.

### First checks

Initial checks should include:

- row count difference,
- missing keys,
- extra keys,
- duplicate source keys,
- duplicate target keys,
- aggregate sum difference,
- basic metric comparisons.

### First artifacts

Initial artifacts should include:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
target/run_results.json
target/failures/
reports/
```

## Mid-term goals

### Query-capable contracts

Support relation-based and query-based source/target outputs.

This is important for canonical compare views, surrogate-key differences, business-key mapping, and migration validation.

### CDC validation

Add explicit CDC validation support for:

- freshness,
- incremental windows,
- upsert-style CDC,
- operation-column CDC,
- soft deletes,
- hard deletes,
- late-arriving data.

### Schema policies

Support schema comparison with explicit technical-column ignores and compatibility rules.

### State

Add state support for:

- watermarks,
- sample keys,
- previous failed keys,
- run history.

## Ecosystem goals

### Adapter packages

Long-term adapter packages include:

```text
recon-postgres
recon-mysql
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

### Adapter test kit

Create a shared adapter test kit after the typed check-plan and adapter API
contracts stabilize.

The test kit should validate adapter API version compatibility, metadata,
capabilities, SQL rendering for typed operations, and minimal check
compatibility.

### Check and policy packages

Future packages may include:

```text
recon-checks-cdc
recon-checks-migration
recon-checks-medallion
recon-policies-sampling
recon-policies-tolerances
recon-evidence-templates
```

### Recon Hub

Create a lightweight package and adapter index after real packages exist.

## Long-term direction

Recon should become the first tool teams think of when they need to prove source-target data equivalence in a versioned, repeatable, evidence-producing way.

## Roadmap principle

Build one serious core first, then grow the ecosystem.
