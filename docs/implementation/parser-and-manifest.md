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

- the shared parsed-project loader discovers contract, local check-pack,
  sampling-policy, tolerance-policy, schema-policy, and macro source files,
- the shared parsed-project loader parses contract resources only,
- parse and compile use authored files as the source of truth rather than
  requiring `recon compile` to read `target/manifest.json`,
- source locations are currently path-level; best-effort line and column
  locations are future diagnostic improvements.

Future non-contract resource loading should follow
`docs/decisions/adr-0017-project-resource-loading-and-precedence.md`.
Resource discovery should be catalog-driven rather than a set of ad hoc loops.
The shared loader should remain the single source of truth for parse and
compile.

Non-contract resource indexing introduces file metadata, not resource semantics.
The shared loader discovers local check-pack, sample-policy, tolerance-policy,
schema-policy, and macro files through a catalog, computes deterministic
checksums, and includes those source files in the parsed-project file list. It
continues to parse only contract resources until each non-contract resource
schema is implemented.

The resource catalog controls missing path behavior separately for defaulted
paths and authored paths. `required_by_default` controls missing default paths;
`explicit_missing_is_error` controls missing authored paths. Existing files that
are not directories remain invalid resource paths.

Index-only non-contract resources should not be YAML-validated, rendered,
executed, reference-validated, or summarized as named resources. Duplicate
resource-name validation applies only after a resource kind has a parsed model
with a locked name field.

Same-kind overlapping resource paths may deduplicate the same real file, but a
source file reachable through multiple resource kinds must fail with
`RC_PARSE_AMBIGUOUS_RESOURCE_FILE`. The loader must not silently classify one
file as the first matching kind.

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

For current non-contract source-file indexing, non-contract local files appear
only in the existing `files` map with the current file-record shape:

```json
{
  "path": "macros/normalize_email.sql",
  "resource_type": "macro_file",
  "checksum": "..."
}
```

Expected resource types for file-level indexing are:

- `contract`,
- `check_pack`,
- `sample_policy`,
- `tolerance_policy`,
- `schema_policy`,
- `macro_file`.

Endpoint resource files remain out of scope until `endpoint-paths` and endpoint
reference semantics are locked.

When package resources are implemented, resource files should have
namespace-qualified in-memory IDs such as:

```text
<namespace>://<relative_path>
```

Manifest changes for non-contract resources must follow compatibility rules in
`docs/compatibility/artifact-versions.md`.

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

Per ADR 0017, duplicate names are errors within the same resource kind and
namespace. Unqualified package references should not be resolved by search
precedence; package and framework resources must be referenced with their
namespace.

When check-pack resources are loaded, package-provided check packs that accept
invocation config must declare valid config schemas. Invalid schemas should fail
parse with `RC_PARSE_INVALID_CHECK_PACK_CONFIG_SCHEMA` before the compiler tries
to validate contract invocations.

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
