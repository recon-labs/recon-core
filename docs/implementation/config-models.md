# Config Models

## Purpose

This document defines implementation expectations for configuration models.

Config models should turn project files and resource files into typed structures that the parser, compiler, runner, and artifact writers can use safely.

## Project config

`recon_project.yml` should map to a typed `ProjectConfig`.

Suggested fields:

```python
@dataclass(frozen=True)
class ProjectConfig:
    name: str
    version: str | None
    config_version: int
    profile: str | None
    contract_paths: list[str]
    sample_policy_paths: list[str]
    tolerance_policy_paths: list[str]
    schema_policy_paths: list[str]
    check_pack_paths: list[str]
    macro_paths: list[str]
    target_path: str
    report_path: str
    state_path: str
```

Default paths may be applied by the config loader.

## Profiles config

Profiles should describe connection definitions.

Real profiles should not be committed.

Suggested model:

```python
@dataclass(frozen=True)
class ProfileConfig:
    name: str
    connections: dict[str, ConnectionConfig]
```

```python
@dataclass(frozen=True)
class ConnectionConfig:
    name: str
    type: str
    raw_config: dict[str, Any]
```

Connection details should remain adapter-specific.

## Resource config

Resources include:

- contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoint definitions,
- macros.

Each resource should include a stable name and source location.

```python
@dataclass(frozen=True)
class SourceLocation:
    path: str
    line: int | None = None
    column: int | None = None
```

## Authored contract model

The authored contract model preserves user intent.

It should not already contain fully resolved defaults or expanded check packs.

Suggested top-level fields:

```python
@dataclass(frozen=True)
class AuthoredContract:
    name: str
    version: int
    source: AuthoredEndpoint
    target: AuthoredEndpoint
    grain: AuthoredGrain | None
    columns: AuthoredColumns | None
    metrics: list[AuthoredMetric]
    checks: AuthoredChecks
    sampling: AuthoredSampling | None
    tolerance_policy: str | None
    schema: AuthoredSchemaPolicy | None
    cdc: AuthoredCdcPolicy | None
    evidence: AuthoredEvidence | None
    owners: dict[str, str]
    tags: list[str]
    source_location: SourceLocation
```

`AuthoredCdcPolicy` should preserve CDC identity separately from `grain`.
`cdc.keys` may declare explicit keys or `same_as: grain`; it should not be
resolved by the parser.

## Unknown fields

Unknown fields should produce diagnostics.

Recommended default:

- error for unknown fields in strict schema areas,
- warning only where extension fields are intentionally allowed.

## Naming rules

Contract names should be unique within a project.

Check names should be unique within a compiled contract.

Metric names should be unique within a contract.

Policy names should be unique per policy type.

## Source locations

All parsed resources should preserve file path and best-effort line/column information.

This enables actionable diagnostics.

## Serialization

Config and resource models should support serialization to JSON/YAML artifact shapes.

Do not serialize Python-specific implementation details.

## Design principle

Config models should make invalid states hard to represent and diagnostics easy to produce.
