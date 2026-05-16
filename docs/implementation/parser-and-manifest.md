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

## Manifest responsibilities

The manifest should contain:

- artifact type and version,
- project metadata,
- resource graph,
- contract summaries,
- policy summaries,
- check pack summaries,
- endpoint summaries,
- file paths,
- selectors,
- parse diagnostics.

## Manifest shape

Example:

```json
{
  "artifact_type": "manifest",
  "artifact_version": 1,
  "project": {
    "name": "ecommerce_recon",
    "config_version": 1
  },
  "contracts": {
    "customer_revenue": {
      "name": "customer_revenue",
      "path": "contracts/customer_revenue.yml",
      "tags": ["finance"],
      "source": {
        "connection": "legacy",
        "relation": "qa.v_customer_revenue_compare"
      },
      "target": {
        "connection": "warehouse",
        "relation": "qa.v_customer_revenue_compare"
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
- duplicate policy names,
- invalid scalar/list/object types,
- unknown resource type,
- missing required contract fields that do not require compile-time resolution.

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

## Defaults

File-level and project-level defaults may be parsed, but they should be resolved during compilation.

The manifest may record defaults as authored resources.

## Diagnostics

Diagnostics should include file path and resource name.

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

## Design principle

Parsing understands the project. It does not decide exactly what will run.
