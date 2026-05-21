# Domain Models

## Core model groups

Recon should separate authored models, parsed models, compiled models, execution models, and result models.

## Authored models

Authored models represent user input.

Examples:

```text
AuthoredContract
AuthoredCheck
AuthoredMetric
AuthoredSamplingConfig
AuthoredToleranceConfig
AuthoredSchemaPolicy
AuthoredCdcPolicy
```

These models should preserve enough location information for useful diagnostics.

## Parsed models

Parsed models represent validated project resources.

Examples:

```text
ParsedProject
ParsedContract
ParsedCheckPack
ParsedSamplePolicy
ParsedTolerancePolicy
ParsedSchemaPolicy
ParsedEndpoint
```

Parsed models should be structurally valid but not necessarily execution-ready.

## Manifest model

The manifest is the machine-oriented project graph.

It should include:

- project metadata,
- contract resources,
- check pack resources,
- policy resources,
- selectors,
- resource file paths,
- resource IDs,
- parse diagnostics.

## Compiled models

Compiled models are explicit execution-ready definitions.

Examples:

```text
CompiledProject
CompiledContract
CompiledCheck
CompiledMetric
CompiledSampling
CompiledTolerance
CompiledSchemaPolicy
CompiledCdcPolicy
```

Compiled models should show all resolved behavior.

Compiled checks should include identity and requirement metadata, including
whether they use comparison identity from `grain.keys`, CDC identity from
`cdc.keys`, or no key identity.

The current compiled model should assume one default comparison identity and
one default CDC identity per contract. Future named identities should be modeled
explicitly rather than by passing raw key lists through checks.

Likely future model concepts:

```text
IdentityDefinition
IdentityRef
ResolvedIdentity
CheckIdentityRequirement
```

Those concepts need a future decision before multi-grain or multi-CDC-key
contracts are implemented.

## Execution models

Execution models represent work to be run.

Examples:

```text
ExecutionPlan
CheckJob
SqlQuery
AdapterRequest
FailureQuery
```

## Result models

Result models represent what happened.

Examples:

```text
RunResult
ContractResult
CheckResult
FailureDetail
EvidenceReference
Diagnostic
```

Check results for blocked checks should include the failed prerequisite checks
and a skip reason.

## Identifiers

Resource identifiers should be stable.

Contracts should have unique names within a project.

Generated check IDs should be deterministic when possible.

Example:

```text
contract_name.check_name
customer_revenue.revenue_by_month
```

## Source locations

Parsed resources should preserve source file and line/column where feasible.

This enables actionable errors.

## Diagnostics

Diagnostics should be structured and reusable.

Fields may include:

- severity,
- code,
- message,
- resource type,
- resource name,
- file path,
- location,
- hint.

## Serialization

Manifest, compiled artifacts, and run results should be serializable.

Human-readable artifacts may be YAML.

Machine-readable artifacts may be JSON.

## Design principle

Keep authored, parsed, compiled, executed, and result models separate so behavior is easier to reason about and test.
