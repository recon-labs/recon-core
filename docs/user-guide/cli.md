# CLI

## Overview

Recon is designed as a CLI-first framework.

Core commands:

```bash
recon init
recon parse
recon compile
recon run
```

Current implementation status:

- `recon init` is implemented.
- `recon parse` is implemented for structural contract parsing, local resource
  file indexing, and manifest generation.
- `recon compile` is implemented for the current compiler scope.
- `recon compile --render-sql` is implemented for DuckDB relation endpoints
  and current typed check-plan operations.
- `recon run` is registered but not implemented yet.

## `recon init`

Creates a starter Recon project.

Expected command:

```bash
recon init ecommerce_recon
```

Expected output:

```text
recon_project.yml
.gitignore
connections/profiles.yml.example
contracts/
check_packs/
macros/
sample_policies/
tolerances/
schema_policies/
target/
reports/
state/
```

`check_packs/`, `sample_policies/`, `tolerances/`, `schema_policies/`, and
`macros/` are indexed by `recon parse` as source-file metadata in
`target/manifest.json`. Recon still parses contract YAML only; local
check-pack, policy, and macro semantics remain future work.

`recon init` should not overwrite an existing path unless an explicit overwrite option is added later.

`PROJECT_NAME` must be a single directory name that can be used in stable
compiled artifact IDs. It must start with a letter or underscore and contain
only letters, numbers, and underscores. It must not be an absolute path, a
nested path, or contain path traversal.

## `recon parse`

Validates authored project structure and writes a manifest.

```bash
recon parse
```

Expected output:

```text
target/manifest.json
```

Current `parse` behavior:

- loads `recon_project.yml`,
- discovers configured contract files and indexable local resource files,
- loads duplicate-key-safe YAML,
- parses single-contract files and simple `contracts:` multi-contract files,
- validates required contract fields,
- validates source and target endpoint shape,
- rejects unknown top-level contract fields,
- detects duplicate contract names,
- records local check-pack, sampling-policy, tolerance-policy, schema-policy,
  and macro source files in `target/manifest.json.files`,
- writes parse diagnostics into `target/manifest.json`.

If project config loads but contract parsing fails, `recon parse` still writes
`target/manifest.json` with diagnostics and exits with code `2`.

If one entry in a multi-contract file is invalid, valid entries from that file
are still included in the manifest while diagnostics report the invalid entry.

Malformed YAML diagnostics are concise and do not print raw YAML parser
snippets. Contract endpoints may include source/target query text or private
literals, so terminal output and manifest diagnostics summarize invalid YAML
without echoing the offending line.

If project root discovery or project config loading fails, `recon parse` exits
with code `4` and does not write a manifest.

If the manifest cannot be written, `recon parse` exits with code `3` and prints
a runtime diagnostic.

`recon parse` rejects symlinked manifest output paths instead of following them
when writing `target/manifest.json`.

`recon parse` does not parse local check-pack or policy files into named
resources, validate references to them, render or execute macros, compile
checks, expand check packs, resolve sampling or tolerances, validate adapter
capabilities, execute queries, or produce evidence.

## `recon compile`

Generates human-readable execution artifacts.

```bash
recon compile
```

Expected output:

```text
target/compiled_contracts/
target/compiled_checks/
```

For optional adapter-aware SQL rendering with the in-core DuckDB local
development adapter, install `recon-core[duckdb]`, create
`connections/profiles.yml`, and set any referenced environment variables such as
`RECON_DUCKDB_PATH` before running:

```bash
recon compile --render-sql
```

`compile` should resolve defaults, refs, check packs, metrics, sampling,
tolerances, schema policies, CDC behavior, and adapter capabilities. SQL files
under `target/compiled_sql/` are produced only by optional adapter-aware compile.

Current `compile` behavior:

- loads project configuration,
- discovers local resource files through the shared parser and parses contract
  files only,
- expands `recon_core.basic_equivalence`,
- compiles explicit `sum` metrics into aggregate comparison checks,
- removes old top-level compiled contract and compiled checks YAML files once
  `target-path` is known,
- rejects symlinked compiled artifact directories and symlinked `target-path`
  ancestry, and rejects exact compiled artifact output paths that are symlinks,
  directories, or other non-files,
- writes `target/compiled_contracts/<contract_name>.yml`,
- writes `target/compiled_checks/<contract_name>.yml`,
- sets `rendering.status: not_rendered` for plain compile,
- supports optional `--render-sql` for adapter-aware rendering,
- loads `connections/profiles.yml` only when `--render-sql` is requested,
- resolves the selected profile target and only the named connections
  referenced by compiled contracts,
- requires source and target DuckDB connections for a contract to resolve to the
  same adapter connection config; cross-connection rendering is not implemented,
- validates literal profile adapter type, resolved adapter metadata, adapter API
  compatibility, and required capabilities before writing SQL,
- writes `target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql`
  plus target-relative `rendering.sql_paths` and `rendering.adapter_type` when
  SQL rendering succeeds,
- sets rendering status to `rendered`, `blocked`, or `failed` for
  adapter-aware compile results,
- writes no compiled SQL files and marks checks `blocked` or `failed` when any
  rendering diagnostic prevents adapter-aware SQL artifact output; checks blocked
  only because SQL output was suppressed include a suppression diagnostic in
  their compiled checks artifact,
- removes stale `target/compiled_sql/` output on plain compile,
- validates duplicate contract names and stable ID-safe project, contract, and
  metric names before writing compiled artifacts,
- validates case-insensitive contract filename collisions before writing
  compiled artifacts,
- rejects unsupported check-pack invocation config, nested `checks` mappings
  with non-string keys, unknown metric fields, invalid sampling config, and
  contracts that compile into no checks,
- rejects projects where no contracts are discovered,
- exits with code `2` when parse or compile diagnostics contain errors.

Current limitations:

- explicit authored checks outside supported check-pack and metric compilation
  fail with a clear diagnostic,
- adapter-aware rendering is relation-only; `source.query` and `target.query`
  endpoints return clear unsupported diagnostics for `--render-sql`,
- DuckDB `--render-sql` currently targets one adapter connection context and
  does not attach or bridge multiple DuckDB database files,
- the in-core DuckDB adapter renders SQL but does not execute checks or fetch
  metadata yet,
- execution, run results, and evidence reports are not implemented yet.

## `recon run`

Executes checks. This command is not implemented yet.

```bash
recon run
```

Planned future output:

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

Recommended exit code categories:

```text
0  success
1  check failure with error severity
2  parse, validation, or compile error
3  execution or runtime error
4  configuration error
```

When a command fails, Recon should print concise diagnostic output:

```text
Error: <message>
Code: <diagnostic code>
Message: <diagnostic message>
Path: <path when available>
Hint: <fix when available>
```

## Selectors

Future illustrative selector examples by gated stage:

Minimal contract/path selector examples:

```bash
recon compile --select "contract:customer_revenue"
recon compile --render-sql --select "path:contracts/revenue/customer_revenue.yml"
recon run --select "contract:customer_revenue"
```

Later gated selector examples:

```bash
recon run --select "selector:critical_reconciliations"
recon run --select "check:customer_revenue.row_count"
recon run --exclude "contract:experimental_*"
```

Selectors are not implemented yet, and the exact selector syntax is not locked.
Before adding `--select`, `--exclude`, or `selectors.yml`, Recon needs a
selector design covering syntax, manifest metadata, partial compile/run
behavior, and run result semantics.

Selector support should be introduced in stages. The first implementation should
stay narrow around explicit contract/path scope for compile, SQL rendering, and
run. Named selectors, check-level selectors, tag/domain/package selectors,
state/result selectors, and richer composition remain later design work.
Contract-only exclusion, including simple contract-name patterns such as
`contract:experimental_*`, may be included in the first selector implementation
only if the selector gate locks pattern syntax and select/exclude precedence;
otherwise it remains part of richer selector expansion.

Selectors should use parsed project metadata rather than scanning files
independently from the parser.

Future `path:...` selectors should match project-relative manifest paths such
as `contracts/revenue/customer_revenue.yml`. Exact file-path selection should be
defined before directory-prefix selection. Selecting a multi-contract YAML file
should include all contracts in that file unless a later selector design
explicitly combines file selection with a narrower contract or check selector.
Metrics currently live inside contracts, so contract/path selectors select the
metric-generated checks for the selected contracts; individual metric/check
selection waits for later `check:...` support.

## Artifact directories

Generated artifacts should be written under:

```text
target/
reports/
state/
```

These should be gitignored.
