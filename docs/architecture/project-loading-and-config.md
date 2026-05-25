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

The loader should discover resources from configured paths:

- contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoints,
- macros.

Current implementation status:

- project configuration preserves path fields for these resource categories,
- parse and compile currently discover and load contract files only,
- non-contract local resource loading is gated until resource model boundaries,
  duplicate rules, package/local precedence, and manifest shape are locked.

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
