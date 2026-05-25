# Parser and Manifest

## Purpose

The parser reads authored files and produces a manifest.

The manifest is a machine-oriented project graph used by compile, run, selectors, docs, CI tooling, and future integrations.

## Parser responsibilities

The parser should:

- locate project root,
- read `recon_project.yml`,
- resolve configured resource paths,
- load YAML files,
- parse resources into typed authored/parsed models,
- validate structural shape,
- detect duplicate resource names,
- record source locations,
- produce diagnostics,
- write `target/manifest.json`.

The parser should not expand check packs or compile metrics into checks.

Current implementation status:

- the shared parsed-project loader discovers and parses contract resources only,
- parse and compile use authored files as the source of truth rather than
  requiring `recon compile` to read `target/manifest.json`,
- source locations are currently path-level; best-effort line and column
  locations are future diagnostic improvements.

## Manifest responsibilities

The manifest should contain:

- artifact type and version,
- Recon version,
- generation timestamp,
- project metadata,
- discovered resource files,
- contract summaries,
- parse diagnostics.

Future parser milestones may add policy summaries, check pack summaries,
endpoint summaries, selectors, and richer resource graph metadata.

## Manifest shape

Example:

```json
{
  "artifact_type": "manifest",
  "artifact_version": 1,
  "recon_version": "0.0.0",
  "generated_at": "2026-05-20T12:00:00Z",
  "project": {
    "name": "ecommerce_recon",
    "config_version": 1,
    "version": "0.1.0"
  },
  "files": {
    "contracts/customer_revenue.yml": {
      "path": "contracts/customer_revenue.yml",
      "resource_type": "contract",
      "checksum": "..."
    }
  },
  "contracts": {
    "customer_revenue": {
      "name": "customer_revenue",
      "version": 1,
      "path": "contracts/customer_revenue.yml",
      "tags": ["finance"],
      "source": {
        "connection": "legacy",
        "relation": "qa.v_customer_revenue_compare",
        "query": null
      },
      "target": {
        "connection": "warehouse",
        "relation": "qa.v_customer_revenue_compare",
        "query": null
      }
    }
  },
  "diagnostics": []
}
```

## Structural validation

Parse-time validation should catch:

- invalid YAML,
- invalid top-level resource shape,
- missing required project config,
- duplicate contract names,
- invalid scalar/list/object types,
- unknown resource type,
- missing required contract fields that do not require compile-time resolution.

Future parser milestones should add duplicate-resource validation for policy,
check-pack, endpoint, and macro resources after the non-contract resource loader
is designed.

## Multi-contract files

Parser should support both:

```yaml
version: 1
name: customer_revenue
...
```

and:

```yaml
version: 1
contracts:
  - name: customer_revenue
  - name: customer_status
```

Internally both should normalize into a list of parsed contracts.

If a multi-contract file contains both valid and invalid entries, valid
contracts should still appear in the manifest while parse diagnostics report
the invalid entries.

## Defaults

File-level and project-level defaults may be parsed, but they should be resolved during compilation.

The manifest may record defaults as authored resources.

## Diagnostics

Diagnostics should include file path and resource name. Line and column fields
may be added when parser source-location support is expanded.

Example:

```json
{
  "code": "RC_PARSE_DUPLICATE_CONTRACT",
  "severity": "error",
  "message": "Contract name customer_revenue is defined more than once.",
  "resource_type": "contract",
  "resource_name": "customer_revenue",
  "path": "contracts/customer.yml"
}
```

## Output path

Default manifest path:

```text
target/manifest.json
```

The writer should create the target directory when needed.

The manifest writer should overwrite the current `manifest.json` during normal
regeneration, but generated manifest paths must remain real paths. It should
reject symlinked `target-path` ancestry and exact `manifest.json` output
symlinks instead of following them.

If the manifest cannot be written, `recon parse` should return a structured
runtime diagnostic instead of crashing.

## Design principle

Parsing understands the project. It does not decide exactly what will run.
