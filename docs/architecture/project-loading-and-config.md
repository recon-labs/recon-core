# Project Loading and Configuration

## Project root

Recon should locate the project root by finding:

```text
recon_project.yml
```

Commands should run from the project root or a subdirectory.

## Project configuration

`recon_project.yml` defines project-level settings.

Example:

```yaml
name: ecommerce_recon
version: 0.1.0
config-version: 1

profile: dev

contract-paths:
  - contracts

sample-policy-paths:
  - sample_policies

tolerance-policy-paths:
  - tolerances

schema-policy-paths:
  - schema_policies

check-pack-paths:
  - check_packs

macro-paths:
  - macros

target-path: target
report-path: reports
```

## Path resolution

Paths should be resolved relative to the project root unless explicitly absolute.

Generated paths should default to:

```text
target/
reports/
state/
```

## Profiles

Connection profiles should be separate from project logic.

Recommended files:

```text
connections/profiles.yml.example
connections/profiles.yml
```

The example file is versioned. The real profile file is ignored.

## Environment variables

Profiles should support environment variable references.

Example:

```yaml
password: "{{ env_var('WAREHOUSE_PASSWORD') }}"
```

Missing environment variables should produce clear configuration errors.

## Packages

`packages.yml` should describe future package dependencies.

Installed package resources should live under:

```text
recon_packages/
```

This directory should be ignored.

## Selectors

`selectors.yml` should define named contract selections.

Selector behavior should operate on manifest metadata rather than raw file scans.

Selector syntax and semantics are not locked yet. Project loading may preserve
the future resource location, but implementation of `selectors.yml`,
`--select`, `--exclude`, or partial compile/run behavior requires a future
selector decision.

## Resource discovery

Resource loading and precedence are locked by
`docs/decisions/adr-0017-project-resource-loading-and-precedence.md`.

The loader should be catalog-driven. Each resource kind should define its path
field, accepted suffixes, parser or indexer, required/default path behavior,
packageability, manifest inclusion, and reference-resolution behavior.

Before non-contract discovery is implemented, project configuration and path
resolution should preserve whether each resource path was authored or defaulted.
The loader needs that origin to skip missing default optional directories while
failing explicitly configured missing optional paths.

The loader should discover resources from configured paths:

- contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoints,
- macros.

`endpoint-paths` is a future config field. Endpoint resources are documented as
a target resource kind, but current `ProjectConfig` does not load endpoint
paths yet.

Current implementation status:

- project configuration preserves path fields for these resource categories,
- parse and compile currently discover and load contract files only,
- non-contract local resource loading is designed by ADR 0017 but is not
  implemented yet.

Locked design:

- `contract-paths` are required,
- default non-contract resource paths are optional and may be absent,
- explicitly configured non-contract resource paths must exist and be
  directories,
- unqualified resource references resolve only in the root project namespace,
- package and framework resources must be referenced as
  `<namespace>.<resource_name>`,
- `recon_core` is reserved for framework built-ins,
- check-pack invocation config schemas follow ADR 0018 when check-pack
  resources are loaded,
- macros may be discovered and checksummed but are not parsed or executed until
  macro semantics are locked.

Milestone 4.6 should implement local non-contract resource discovery as
source-file indexing only. It should add file metadata for check packs, sample
policies, tolerance policies, schema policies, and macros to the shared parsed
project and manifest `files` map, but it should not create parsed resource
summaries, validate references, expand custom check packs, load endpoint
resources, or introduce package loading.

Milestone 5 validation should not validate references to local check packs,
sampling policies, tolerance policies, schema policies, endpoint resources, or
macros until those resources are loaded through one shared project-loading
model.

## Configuration precedence

Recommended precedence:

1. check-level setting,
2. contract-level setting,
3. file-level defaults,
4. project-level setting,
5. package default,
6. framework default.

This precedence applies to resolved settings and defaults. Resource reference
resolution is stricter: local unqualified references resolve only locally, while
package and framework references must be qualified.

## Validation

Project loading should validate:

- required config fields,
- path existence where required,
- duplicate resource names,
- invalid config keys,
- unsafe profile handling,
- generated artifact path conflicts.

## Design principle

Project loading should be predictable, explicit, and safe with credentials.
