# CLI

## Overview

Recon is designed as a CLI-first framework.

Core commands:

```bash
recon parse
recon compile
recon run
```

Additional expected command:

```bash
recon init
```

## `recon init`

Creates a starter Recon project.

Expected command:

```bash
recon init ecommerce_recon
```

Expected output:

```text
recon_project.yml
connections/profiles.yml.example
contracts/
sample_policies/
tolerances/
schema_policies/
```

## `recon parse`

Validates project structure and writes a manifest.

```bash
recon parse
```

Expected output:

```text
target/manifest.json
```

`parse` should check YAML syntax, required fields, duplicate contract names, resource discovery, and basic refs.

## `recon compile`

Generates human-readable execution artifacts.

```bash
recon compile
```

Expected output:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
```

`compile` should resolve defaults, refs, check packs, metrics, sampling, tolerances, schema policies, CDC behavior, and adapter capabilities.

## `recon run`

Executes checks.

```bash
recon run
```

Expected output:

```text
target/run_results.json
target/failures/
reports/
```

`run` should parse and compile automatically when needed.

## Exit codes

Expected behavior:

- zero when all error-severity checks pass,
- non-zero when error-severity checks fail or execution cannot continue,
- configurable behavior for warnings later.

## Selectors

Future selector examples:

```bash
recon run --select tag:critical
recon run --select contract:customer_revenue
recon run --exclude tag:experimental
```

Selectors should use parsed project metadata.

## Artifact directories

Generated artifacts should be written under:

```text
target/
reports/
state/
```

These should be gitignored.
