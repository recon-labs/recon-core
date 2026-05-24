# ADR 0013: Typed Check Plans and Adapter SQL Rendering

## Context

Recon is a source-target reconciliation framework. It must compare outputs across
systems with different SQL dialects, metadata behavior, type systems, timestamp
semantics, null behavior, hashing behavior, and connection requirements.

Recon also needs generated artifacts that explain:

- what the user authored,
- what Recon compiled,
- which checks will run,
- which SQL or adapter operations will run,
- which assumptions, capabilities, and validations apply.

dbt Core is a mature open-source reference for adapter boundaries. dbt separates
database-specific behavior into adapter packages, exposes adapter methods during
compilation, supports adapter dispatch for database-specific macros, provides
cross-database macro helpers, and maintains shared adapter tests.

Recon should learn from dbt's adapter maturity, but Recon's domain is different.
dbt compiles transformation SQL. Recon compiles reconciliation behavior that must
be inspectable as evidence and safe across source-target systems.

## Decision

Recon Core will use a typed check-plan architecture.

Core owns reconciliation semantics:

- authored and compiled contract models,
- check definitions and check-pack expansion,
- validation rules,
- compiled check models,
- typed check plan models,
- result models,
- evidence models,
- base adapter interfaces,
- adapter capability requirements.

Adapters own system-specific behavior:

- connection lifecycle,
- query execution,
- metadata retrieval,
- relation and identifier behavior,
- type mapping,
- SQL dialect rendering,
- adapter capability declarations,
- adapter-specific tests.

Compiler and check planning should produce typed abstract operations rather than
database-specific SQL as the primary internal representation.

Typed operation models must validate their payload shape. An operation should
accept only the fields that are meaningful for that operation type, and planned
operation names must not be emitted until their payload schema and capability
requirements are implemented and tested.

Examples of typed operations:

```text
row_count
aggregate
grouped_aggregate
key_diff
duplicate_key
null_safe_equal
cast
limit
hash
timestamp_diff
schema_metadata
```

SQL adapters render these operations into dialect-specific SQL.

Non-SQL or semi-structured adapters may later translate typed plans into
projection or execution requests without pretending that all systems are SQL.

Generated compiled artifacts should include both the typed plan summary and any
rendered SQL that will be executed.

## Adapter API Versioning

The adapter API should be versioned.

Each adapter should declare:

```text
adapter_type
adapter_version
supported_adapter_api_version
capabilities
```

Core should reject or warn on incompatible adapter API versions before execution.

When a typed operation is added or changed, adapters must either:

- implement rendering/execution for the operation, or
- explicitly declare the capability as unsupported.

Unsupported required capabilities should produce clear compile or validation
diagnostics.

## Capability Model

Capabilities should be granular enough to prevent false portability.

Examples:

```text
relations
queries
metadata_columns
metadata_precision_scale
temp_tables
cte_support
null_safe_equality
timestamp_diff
numeric_cast
string_cast
safe_hash_expression
portable_hash_compatible
json_path
semi_structured_projection
```

Hash behavior must be conservative. An adapter must not claim portable hash
compatibility unless cross-adapter behavior is intentionally implemented and
tested.

## Relationship to dbt

Recon will follow dbt's mature adapter boundary pattern:

- adapter packages are separate from the core framework over time,
- adapters provide database-specific behavior,
- shared adapter tests protect adapter compatibility,
- adapter authors get a clear interface and test suite.

Recon will not use dbt-style macro dispatch as the primary comparison engine.

Macro dispatch is useful for SQL transformation frameworks, but Recon needs a
typed, inspectable, evidence-oriented execution plan. Hidden SQL-generation
behavior would make it harder to validate capabilities, explain compiled checks,
debug generated SQL, and prevent unsafe comparisons.

Macros, SQL builders, or SQLGlot-style tooling may be used later as
implementation helpers, but they are not the public core-adapter contract.

## Testing Strategy

Core tests should include:

- compiler tests for authored contract to compiled checks,
- check-pack expansion tests,
- metric compilation tests,
- typed plan generation tests,
- capability requirement tests,
- unsupported capability diagnostics,
- generated artifact shape tests.

Adapter tests should include:

- adapter registry tests,
- connection lifecycle tests,
- metadata tests,
- identifier quoting tests,
- operation rendering golden tests,
- capability declaration tests,
- minimal end-to-end check compatibility tests.

A shared adapter test kit should be created before production adapters are split
into separate repositories.

Every production adapter repository should run the shared adapter test kit in CI.

## Alternatives Considered

### Put all comparison and SQL logic in core

Rejected.

This would make core dependent on every database dialect and driver, creating
large dependency bloat and high-risk changes whenever one dialect needs a fix.

### Put comparison semantics inside adapters

Rejected.

This would fragment Recon's behavior and make checks inconsistent across
systems. Core must define what reconciliation means.

### Use dbt-style macro dispatch as the primary engine

Rejected as the primary contract.

dbt-style dispatch is mature and useful, but Recon needs typed compiled plans
and evidence artifacts that show exactly what will run. Macro dispatch can be an
internal helper later, but it should not hide comparison semantics.

### Use blind SQL transpilation as the primary portability layer

Rejected.

SQL transpilation can help with formatting or translation, but reconciliation
correctness depends on metadata, null semantics, timestamps, precision, hashing,
and adapter capabilities. Those require explicit typed behavior and tests.

## Consequences

Core implementation will need typed plan models before a serious check engine.

Adapter implementation will be slightly more formal upfront, but safer long
term.

Adding a new typed operation becomes a controlled API change:

1. update core operation model,
2. update capability declarations,
3. update shared adapter tests,
4. update adapters or mark unsupported,
5. update generated artifacts and diagnostics.

Generated SQL should remain debuggable and traceable back to typed operations.

## Implementation Guidance

Milestone 4 should introduce compiled checks and typed plan models without
requiring production adapters.

Milestone 5 should make validation and capability requirements explicit.

Milestone 6 should implement the first local/dev adapter and the first internal
adapter test-kit shape.

Milestone 7 should execute compiled typed plans through adapters.

Production adapter repositories such as `recon-snowflake` and `recon-postgres`
should split only after the adapter API and shared tests are stable enough.

## References

- dbt adapter creation: `https://docs.getdbt.com/guides/adapter-creation`
- dbt adapter object: `https://docs.getdbt.com/reference/dbt-jinja-functions/adapter`
- dbt dispatch: `https://docs.getdbt.com/reference/dbt-jinja-functions/dispatch`
- dbt cross-database macros: `https://docs.getdbt.com/reference/dbt-jinja-functions/cross-database-macros`
- dbt adapters repository: `https://github.com/dbt-labs/dbt-adapters`
