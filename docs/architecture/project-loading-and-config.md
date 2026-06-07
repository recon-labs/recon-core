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

profile: local

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

Profile loading follows the adapter boundary in
`docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`.
Recon selects one profile and one target. That selected target is the active
environment and contains named connections used by contract `source.connection`
and `target.connection` fields.

Example:

```yaml
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
```

`recon_project.yml` may select the profile:

```yaml
profile: local
```

## Environment variables

Profiles should support environment variable references.

Example:

```yaml
password: "{{ env_var('WAREHOUSE_PASSWORD') }}"
```

Initial profile rendering supports `env_var('NAME')` and
`env_var('NAME', 'default')` for non-routing connection config fields.
Connection `type` values must be literal adapter types because they select the
adapter boundary. For contract-specific adapter rendering or execution, missing
environment variables in referenced connection payloads should produce clear
configuration errors. Missing environment variables in unselected targets or
unreferenced connections should not fail the invocation. Unsupported template
syntax, including `{{ ... }}` expressions, Jinja statements such as `{% ... %}`,
and Jinja comments such as `{# ... #}`, in referenced connection payloads should
fail instead of being passed to adapters as raw text.

Generated artifacts and diagnostics may include profile name, target name,
adapter type, and non-secret relation identifiers. They must not include
secrets or fully rendered credential payloads.

Current implementation loads profiles for `recon compile --render-sql` only.
Plain parse and compile do not require `connections/profiles.yml`. Milestone 6
adapter-aware rendering requires referenced source and target connections to
resolve to the same adapter type and rendered connection config. Distinct
connection configs are blocked rather than implicitly bridged.

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

Project configuration and path resolution preserve whether each resource path
was authored or defaulted. The loader needs that origin to skip missing default
optional directories while failing explicitly configured missing optional paths.

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
- parse and compile discover local non-contract source files for file-level
  indexing,
- parse and compile currently parse semantic resource models for contracts only,
- local check-pack, policy, endpoint, package, and macro semantics remain
  future implementation work under ADR 0017.

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

Milestone 4.6 implements local non-contract resource discovery as source-file
indexing only. It adds file metadata for check packs, sample policies,
tolerance policies, schema policies, and macros to the shared parsed project and
manifest `files` map, but it does not create parsed resource summaries, validate
references, expand custom check packs, load endpoint resources, or introduce
package loading.

Milestone 5 validation should not resolve or validate references to
local/package check-pack resources, sampling policies, tolerance policies,
schema policies, endpoint resources, or macros until those resources are loaded
through one shared project-loading model. Unsupported built-in check-pack names
should still fail validation instead of compiling as silent no-ops.

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
