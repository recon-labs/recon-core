# Reconciliation Taxonomy

## Why taxonomy matters

“Data reconciliation” means different things in different contexts. Recon must be precise about which part of the reconciliation world it serves.

This taxonomy defines the reconciliation types and clarifies Recon’s initial scope.

## 1. Source-target dataset reconciliation

This is Recon’s primary scope.

It means comparing two datasets or outputs to determine whether they are equivalent according to a defined contract.

Examples:

- SQL Server table vs Snowflake table,
- MongoDB collection vs BigQuery table,
- Redshift model output vs Snowflake model output,
- old Spark job result vs new dbt model result,
- bronze layer vs silver layer,
- source system vs warehouse replica.

Typical checks:

- row count,
- missing keys,
- extra keys,
- duplicate keys,
- aggregate comparisons,
- value comparisons,
- numeric/timestamp tolerance,
- freshness lag,
- incremental-window validation,
- sampled row/document diff.

Recon should strongly support this.

## 2. CDC / replication reconciliation

This is a specialized source-target reconciliation use case.

It validates ongoing data movement from operational systems into analytics platforms.

Examples:

```text
MongoDB -> BigQuery
SQL Server -> AWS DMS -> Snowpipe -> Snowflake
Postgres -> Debezium -> Kafka -> Databricks
```

Typical checks:

- latest changed records,
- watermark progression,
- freshness lag,
- missing CDC keys,
- insert/update/delete propagation,
- previous failure retest,
- source max timestamp vs target max timestamp.

Recon should treat CDC reconciliation as a first-class use case.

## 3. Migration / cutover reconciliation

This validates a one-time or phased platform transition.

Examples:

- Redshift to Snowflake,
- Teradata to BigQuery,
- SQL Server reporting mart to Databricks,
- legacy ETL to dbt/Snowpark.

Typical checks:

- parallel-run validation,
- old vs new output,
- row count,
- aggregate totals,
- business metric comparisons,
- sample row diff,
- sign-off evidence.

Recon should support this, but not define itself only as a migration tool.

## 4. Pipeline refactor reconciliation

This validates that a rewritten pipeline produces equivalent output.

Examples:

- Spark job rewritten as dbt,
- Airflow SQL task rewritten as a model,
- Python transformation replaced by SQL,
- old metric calculation replaced by new metric layer.

Typical checks:

- output equivalence,
- grain preservation,
- aggregate stability,
- known intentional differences.

Recon should support this because it is recurring and engineering-driven.

## 5. Medallion layer reconciliation

This validates data movement and transformation across Bronze, Silver, and Gold layers.

Examples:

- Bronze should preserve raw records from source.
- Silver should clean and normalize records.
- Gold should aggregate or reshape business entities.

Typical checks:

- expected row preservation or reduction,
- key coverage,
- aggregate preservation,
- grouped aggregate comparison,
- freshness by layer,
- expected grain changes.

Recon should support this as a framework use case, especially for warehouse/lakehouse teams.

## 6. Business logic equivalence reconciliation

This compares outputs of old and new business logic.

Examples:

- old revenue logic vs new revenue logic,
- old customer status calculation vs new one,
- old churn model feature output vs new feature output,
- legacy dashboard dataset vs governed semantic model.

Typical checks:

- exact value match,
- numeric tolerance,
- grouped aggregate comparison,
- known exception handling,
- business owner sign-off evidence.

Recon should support this where both outputs are explicit datasets or queries.

## 7. Generic data quality validation

This checks one dataset for health.

Examples:

- not null,
- unique,
- accepted values,
- ranges,
- table freshness,
- schema validity.

Recon may include limited dataset-local checks when they support reconciliation, but generic DQ is not Recon’s main category.

Recon should integrate with, not replace, tools like dbt tests, Soda, or Great Expectations.

## 8. Financial/accounting reconciliation

This compares ledgers, balances, settlements, invoices, bank statements, and financial control totals.

Recon may eventually support this through domain-specific check packs, but it should not be the v1 identity.

Possible future package:

```text
recon-checks-finance
```

## 9. MDM / entity resolution reconciliation

This determines whether different records represent the same real-world entity.

Examples:

- fuzzy customer matching,
- golden record creation,
- deduplication across CRM and billing,
- identity resolution.

Recon should not own this in v1.

Recon can compare already-canonicalized entities, but it should not become an MDM platform.

## 10. Statistical/scientific reconciliation

This involves reconciling noisy measurements, model outputs, or scientific observations.

This is outside Recon’s initial scope.

## Recon’s chosen scope

Recon’s first scope is:

> **Reconciliation as Code for source-target data equivalence.**

Included:

- source-target dataset reconciliation,
- CDC reconciliation,
- migration/cutover reconciliation,
- pipeline refactor reconciliation,
- medallion layer reconciliation,
- business output equivalence.

Excluded from v1:

- generic DQ platform,
- MDM/entity resolution,
- automatic fuzzy matching,
- financial close workflow,
- automated data repair,
- ingestion/CDC movement itself.
