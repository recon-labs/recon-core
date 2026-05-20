# ADR 0012: Adapter and Package Ecosystem

## Context

Recon is cross-system by nature.

It may compare Postgres to Snowflake, MySQL to BigQuery, SQL Server to Snowflake, MongoDB to BigQuery, Redshift to Snowflake, Databricks to BigQuery, or other combinations.

Each system has different SQL syntax, metadata behavior, type systems, timestamp behavior, hashing, and connection requirements.

Recon also needs reusable check packs, sampling policies, tolerance policies, schema policies, evidence templates, and examples.

## Decision

Recon Core should be adapter-aware but not adapter-bloated.

Core owns:

- CLI,
- project loading,
- contract parsing,
- contract compilation,
- validation rules,
- result model,
- evidence model,
- base adapter interface,
- built-in core checks and check packs.

Adapters should live in separate packages as the interface stabilizes.

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

Recon resource packages should provide reusable framework resources such as:

- check packs,
- sampling policies,
- tolerance policies,
- schema policies,
- macros,
- evidence templates,
- examples.

## Reasoning

Keeping adapters separate avoids unnecessary dependencies and release coupling.

Keeping resource packages separate allows a community ecosystem to grow without bloating the core runtime.

## Repository strategy

Start with `recon-core`.

Split adapters after the typed check-plan model, adapter API versioning, and
shared adapter test kit stabilize.

Create an adapter test kit when adapter behavior and typed operation rendering
are clear enough to standardize.

Create package loading before building a full Hub.

## Consequences

Core should define clean extension points.

Adapter capabilities should be declared and validated.

The package model should be designed early but implemented after core primitives are useful.

Recon Hub can start later as a static package and adapter index.
