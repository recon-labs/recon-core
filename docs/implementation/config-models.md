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

Current implementation status:

- `ProjectConfig` stores the configured resource path fields,
- contract paths are actively used by parse and compile,
- non-contract resource path fields are preserved configuration surface until
  non-contract resource loading is implemented through ADR 0017.

Future non-contract resource loading should preserve whether each configured
path was authored or defaulted. ADR 0017 requires this so missing default
optional resource directories can be skipped while explicitly configured missing
paths can fail clearly.

Recommended implementation shape:

```python
@dataclass(frozen=True)
class ConfiguredPath:
    value: str
    origin: Literal["defaulted", "authored"]
    field_name: str
```

Path resolution should carry this metadata forward instead of reducing resource
paths to bare `Path` values before discovery. Public config serialization should
continue to expose documented path strings, not Python implementation details.

## Profiles config

Profiles should describe connection definitions.

Real profiles should not be committed.

Profile loading, environment-variable resolution, connection validation, and
secret-safe adapter configuration are future work. They should be implemented
before adapter execution, not folded into project config loading implicitly.

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

Resource loading and reference resolution should follow
`docs/decisions/adr-0017-project-resource-loading-and-precedence.md`.
Resource identity is:

```text
resource_kind + namespace + resource_name
```

Unqualified references resolve only in the root project namespace. Package and
framework references use `<namespace>.<resource_name>`. The `recon_core`
namespace is reserved for framework built-ins.

Milestone 4.6 should not introduce typed config models for local check-pack,
sampling-policy, tolerance-policy, schema-policy, or macro resources. It should
index those files as source-file metadata only until each resource schema is
locked and implemented.

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

`AuthoredColumns` should follow ADR 0019 when typed column parsing is
implemented. Current code preserves authored `columns` as raw contract data.

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

All parsed resources should preserve file path. The current implementation
preserves path-level locations. Best-effort line and column information is a
future diagnostic improvement.

This enables actionable diagnostics.

## Serialization

Config and resource models should support serialization to JSON/YAML artifact shapes.

Do not serialize Python-specific implementation details.

## Design principle

Config models should make invalid states hard to represent and diagnostics easy to produce.
