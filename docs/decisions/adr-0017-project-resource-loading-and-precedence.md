# ADR 0017: Project Resource Loading and Precedence

## Context

Recon project config already exposes path fields for contracts, check packs,
sampling policies, tolerance policies, schema policies, and macros. Public docs
also describe endpoint resources and future packages.

Current implementation loads contract files only. Before Milestone 5 validates
references to non-contract resources, Recon needs a durable rule for:

- which resource kinds are loadable,
- how resource files are discovered,
- how local and package resources are named,
- how unqualified and qualified references resolve,
- how duplicate names fail,
- how missing optional resource directories behave,
- what macro loading means before macro semantics exist.

dbt Core is the main reference. dbt uses a central file-type catalog that maps
resource types to project path fields, extensions, and parser classes. It reads
files across the root project and installed packages, records source files with
project names and checksums, parses resources through resource-specific parser
classes, checks manifest uniqueness after parsing, and rejects duplicate package
project names.

Recon should borrow dbt's resource catalog and namespace discipline, but not
dbt's macro-dispatch model as Recon's primary comparison engine. Core
reconciliation semantics remain typed check plans and explicit validation.

## Decision

Recon will use one shared project resource loading model for parse and compile.

The resource loader will be catalog-driven. Each resource kind must define:

- resource kind,
- configured path field,
- accepted file suffixes,
- whether the default path is required,
- whether explicit missing paths are errors,
- parser or indexer,
- whether the resource is local-only or packageable,
- manifest inclusion behavior,
- reference-resolution behavior.

Parse and compile must not maintain separate resource discovery logic.

## Resource Kinds

The first non-contract resource-loader design targets these kinds:

| Kind | Path field | Suffixes | Required by default | Packageable | Initial handling |
| --- | --- | --- | --- | --- | --- |
| `contract` | `contract-paths` | `.yml`, `.yaml` | Yes | No | Parse authored contracts. |
| `check_pack` | `check-pack-paths` | `.yml`, `.yaml` | No | Yes | Parse/index reusable execution intent using ADR 0018 config-schema rules. |
| `sample_policy` | `sample-policy-paths` | `.yml`, `.yaml` | No | Yes | Parse/index after sampling policy scope is locked. |
| `tolerance_policy` | `tolerance-policy-paths` | `.yml`, `.yaml` | No | Yes | Parse/index after tolerance/null scope is locked. |
| `schema_policy` | `schema-policy-paths` | `.yml`, `.yaml` | No | Yes | Parse/index after schema policy scope is locked. |
| `endpoint` | `endpoint-paths` future field | `.yml`, `.yaml` | No | No initially | Parse/index local reusable endpoints after endpoint refs are locked. |
| `macro_file` | `macro-paths` | `.sql` initially | No | Yes | Discover and checksum only until macro semantics are locked. |

Contracts are project source, not package-provided executable resources.
Packages may include examples, but installed package contract files must not be
loaded into the user's project as executable contracts by default.

Endpoint resources are local-only initially because endpoints usually encode
project-specific connection names, relations, or query assumptions. Package
endpoint resources require a future decision before implementation.

Macro files are not semantic execution rules. Until a future macro decision
exists, macros may be discovered and recorded as source files but must not be
parsed, rendered, executed, or used to validate references.

## Missing Path Behavior

`contract-paths` are required. A configured contract path that does not exist or
is not a directory is an error.

Non-contract default resource paths are optional. If a default optional path is
missing, the loader should skip it without diagnostics.

An explicitly configured non-contract resource path that is missing or is not a
directory is an error.

To support this safely, future config/path models should preserve path origin:

```text
defaulted
authored
```

Until path origin is represented in code, non-contract resource loading should
not treat missing default optional directories as errors.

## Namespaces and Reference Resolution

Every loaded resource belongs to a namespace.

Namespaces:

- the root project namespace is `recon_project.yml:name`,
- each installed package has one package namespace,
- `recon_core` is reserved for framework-provided built-ins.

Resource identity is:

```text
resource_kind + namespace + resource_name
```

Resource names and namespaces should be stable-ID-safe parts. A fully qualified
resource reference has this shape:

```text
<namespace>.<resource_name>
```

Unqualified references resolve only within the root project namespace. They do
not search packages or framework built-ins.

References to package resources or framework built-ins must be qualified. For
example:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

This avoids silent package shadowing and ambiguous resource resolution.

## Duplicate Rules

Duplicate resource names are errors when they occur within the same resource
kind and namespace.

The same resource name may exist in different namespaces, but references must
be qualified to select package or framework resources.

Package namespaces must be unique. A package namespace must not equal the root
project namespace or the reserved `recon_core` namespace.

The root project should not be named `recon_core`.

## Precedence

Resource reference resolution does not use broad search precedence. It is either
local unqualified or exact qualified.

Configuration/default precedence remains separate from resource-reference
resolution:

```text
check-level setting
contract-level setting
file-level default
project-level setting
package default
framework default
```

When defaults are resolved, compiled artifacts must show which source supplied
the resolved behavior.

## Packages

`packages.yml`, `recon deps`, package lock files, and `recon_packages/` remain
future implementation work.

When package loading is implemented:

- package namespaces must be unique,
- installed package count and names should be checked against package metadata
  or a lock file,
- package resources should load through the same resource catalog as local
  resources,
- package resources should not silently override local resources or framework
  built-ins,
- package resource schemas and compatibility ranges must be documented before
  implementation.

This follows dbt's mature pattern of loading a root project plus dependencies
while rejecting duplicate project/package names.

## Manifest and Source Files

Resource files should be tracked with:

- namespace,
- resource kind,
- relative path,
- checksum,
- source location.

For local-only resources, the current manifest file map can remain path based.
When package resources are added, in-memory resource IDs and future manifest
file keys should become namespace-qualified to avoid collisions:

```text
<namespace>://<relative_path>
```

Adding non-contract resource summaries to `target/manifest.json` is an artifact
schema change. Additive optional fields may keep `artifact_version: 1` only when
existing field meanings do not change and readers can ignore unknown fields.
Changing existing manifest key semantics requires compatibility review and may
require an artifact version bump.

## Diagnostics

Resource loading and reference validation must reuse ADR 0016 code-family rules.

Recommended diagnostics:

| Code | Phase | Severity | Meaning |
| --- | --- | --- | --- |
| `RC_PARSE_RESOURCE_PATH_NOT_FOUND` | parse | error | A required or explicitly configured resource path is missing or not a directory. |
| `RC_PARSE_DUPLICATE_RESOURCE_NAME` | parse | error | A resource name is duplicated within the same kind and namespace. |
| `RC_CONFIG_RESERVED_RESOURCE_NAMESPACE` | config | error | A project or package uses the reserved `recon_core` namespace. |
| `RC_CONFIG_DUPLICATE_PACKAGE_NAMESPACE` | config | error | Two packages, or a package and root project, share a namespace. |
| `RC_CONFIG_PACKAGE_NOT_INSTALLED` | config | error | `packages.yml` or a lock file requires a package that is absent from `recon_packages/`. |
| `RC_COMPILE_UNKNOWN_CHECK_PACK` | compile | error | A check-pack reference cannot be resolved. |
| `RC_COMPILE_UNKNOWN_SAMPLE_POLICY` | compile | error | A sampling policy reference cannot be resolved. |
| `RC_COMPILE_UNKNOWN_TOLERANCE_POLICY` | compile | error | A tolerance policy reference cannot be resolved. |
| `RC_COMPILE_UNKNOWN_SCHEMA_POLICY` | compile | error | A schema policy reference cannot be resolved. |
| `RC_COMPILE_UNKNOWN_ENDPOINT` | compile | error | An endpoint reference cannot be resolved. |

Macro reference diagnostics are not locked by this ADR. Macro reference
validation requires a future macro-semantics decision.

## Consequences

Milestone 5 may validate references only for resource kinds that are actually
loaded through the shared resource model.

Until non-contract resource loading exists, validation must continue to fail
clearly for unsupported resource references rather than pretending references
were resolved.

Future package loading, macro semantics, endpoint references, and package
resource schemas remain gated work.

## Alternatives Considered

### Search local resources, packages, and built-ins by precedence

Rejected.

This is convenient but can silently change behavior when a package adds a
resource with the same name as a local resource or another package. Recon should
prefer explicit names over surprising resolution.

### Let local resources override `recon_core` built-ins

Rejected.

Framework built-ins are public behavior. Local customization should use local
names or future explicit extension points, not silent shadowing.

### Parse and execute macros like dbt

Rejected for this phase.

Recon may use macros later as limited helper resources, but comparison
semantics must stay in typed check plans and core-owned validation.

### Treat all missing default resource directories as errors

Rejected.

Optional directories such as `check_packs/`, `tolerances/`, and `macros/` should
not be required for small projects. Explicitly configured missing paths should
still fail.

## Implementation Guidance

Future implementation should introduce a resource catalog before adding
non-contract resource kinds.

Recommended shape:

```text
ResourceKind
ResourceKindSpec
ResourceFile
ResourceReference
ParsedProjectResources
ProjectResourceLoader
```

Tests should cover:

- contract paths remain required,
- default optional resource directories may be absent,
- explicitly configured optional resource paths must exist,
- file path checksums are stable,
- resource discovery is deterministic,
- duplicate names fail within kind and namespace,
- package namespace duplicates fail,
- unqualified package references fail with a hint to qualify,
- qualified `recon_core` built-ins resolve,
- macro files are discovered only as files until macro semantics are locked.

## References

- ADR 0013: Typed Check Plans and Adapter SQL Rendering
- ADR 0016: Validation Timing and Diagnostic Codes
- dbt Core file reader:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/parser/read_files.py`
- dbt Core manifest loader:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/parser/manifest.py`
- dbt Core runtime dependency loading:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/config/runtime.py`
- dbt Core package resolver:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/deps/resolver.py`
