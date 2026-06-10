# Scope and Non-Goals

## Product scope

Recon is an open-source framework for **Reconciliation as Code**.

Recon helps teams define and run equivalence checks between source and target datasets.

Recon’s core responsibility is to answer:

> Does this target output match the source, previous output, replicated system, or expected business result according to a defined equivalence contract?

## In scope

### Equivalence contracts

Recon should define a standard project object called an equivalence contract.

Contracts define:

- source,
- target,
- grain / keys,
- columns or metrics,
- tolerances,
- checks,
- sampling policy,
- evidence policy,
- ownership and severity.

### Source-target comparison

Recon should support comparing:

- relation to relation,
- view to view,
- table to table,
- query to query eventually,
- old output to new output,
- source system to warehouse target,
- medallion layer to medallion layer.

### Existing compare views

Recon should support teams that already have source and target compare views.

This is important because many real reconciliation problems require business-specific joins and canonicalization before comparison.

Recon should not force users to rewrite those queries inside Recon.

### Custom queries

Recon should support custom source and target queries after the relation-first foundation is stable.

This is necessary when:

- source and target surrogate keys differ,
- target uses generated keys,
- comparison requires joins,
- source and target schemas differ,
- canonical output must be produced dynamically.

### Business-key based matching

Recon should compare canonical outputs using business keys, not physical surrogate keys.

Example:

```text
source.customer_id != target.customer_sk
```

Recon should support matching on:

```text
customer_external_id
order_number
policy_number
natural business keys
composite keys
```

### Sampling policies

Recon should support reusable sampling policies.

Important strategies:

- deterministic hash,
- incremental/latest window,
- persisted random sample,
- previous failures retest,
- stratified sampling later,
- high-value/risk-based sampling later.

### Evidence

Recon should generate evidence as a first-class output.

Evidence may include:

- terminal summary,
- JSON run result,
- CSV mismatch details,
- HTML report,
- result tables,
- future approval/sign-off artifacts.

### Adapter ecosystem

Recon Core should define adapter interfaces and basic extension points.

Long term, adapters should live in separate packages:

- `recon-snowflake`,
- `recon-postgres`,
- `recon-sqlserver`,
- `recon-bigquery`,
- `recon-mongodb`.

### Package ecosystem

Recon should support reusable check packs, sampling policies, tolerance policies, and evidence templates.

Long term, these can be distributed through Recon Hub.

## Out of scope for v1

### Generic data quality platform

Recon is not trying to replace general data quality tools.

Recon may include supporting checks, but its identity is source-target equivalence.

### CDC / ingestion tool

Recon does not move data.

It validates data after or alongside movement.

### Warehouse transformation framework replacement

Recon does not transform warehouse data as its main purpose.

It may integrate with transformation workflows, but it does not replace
transformation frameworks.

### Automatic mapping inference

Recon should not guess that source column `cust_id` maps to target column `customer_sk`.

Users must define the equivalence contract.

### MDM / fuzzy entity matching

Recon should not become an entity-resolution or golden-record platform in v1.

### Automated data repair

Recon may identify mismatches, but it should not automatically mutate source or target data in v1.

### SaaS/cloud-first product

Recon starts as an open-source CLI/framework.

Cloud/evidence-vault workflows may come later.

### Heavy UI first

A UI is not required for the core framework.

Docs, CLI, artifacts, and reports come first.

## Scope discipline

When new features are proposed, ask:

1. Does this help prove source-target equivalence?
2. Does this strengthen equivalence contracts?
3. Does this improve repeatability, sampling, or evidence?
4. Does this fit an open-source framework?
5. Does this risk turning Recon into generic DQ or ingestion?

If a feature does not support the core mission, it should be deferred or moved to a future package.
