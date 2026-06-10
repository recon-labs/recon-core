# Project Structure

## Recommended structure

```text
recon_project/
  recon_project.yml
  packages.yml
  selectors.yml

  connections/
    profiles.yml.example

  endpoints/
    sources.yml
    targets.yml

  contracts/
    customer/
      customer_revenue.yml
    orders/
      orders_cdc.yml

  check_packs/
    company_standard.yml

  sample_policies/
    full.yml
    stable_hash_5_percent.yml
    latest_changed_records.yml

  tolerances/
    default.yml
    finance.yml

  schema_policies/
    default.yml
    cdc_metadata.yml

  macros/
    sql/

  target/
  reports/
  state/
```

## Versioned files

Version these:

```text
recon_project.yml
packages.yml
selectors.yml
connections/profiles.yml.example
contracts/
check_packs/
sample_policies/
tolerances/
schema_policies/
macros/
docs/
```

`selectors.yml` is a future project resource for named selector definitions.
Its syntax is not locked yet, and `recon run --select` /
`recon compile --select` are not implemented. Minimal future contract/path
selectors should not require `selectors.yml`.

`recon parse` indexes local check-pack, sampling-policy, tolerance-policy,
schema-policy, and macro files as source-file metadata in
`target/manifest.json`. Recon still parses contract YAML only. Local
check-pack, policy, endpoint, and macro semantics, reference validation, and
package loading remain future work.

## Ignored files

Ignore these:

```text
connections/profiles.yml
.env
target/
reports/
state/
recon_packages/
```

`connections/profiles.yml` contains uncommitted connection profiles. Initial
adapter-aware behavior selects one profile and target environment, then
resolves contract `source.connection` and `target.connection` names against the
selected target's named connections. Secrets and fully rendered credentials
must not be written to generated artifacts.
Connection `type` values must be literal adapter types such as `duckdb`;
`env_var(...)` is for non-routing connection config values. Resolved adapter
`adapter_type` metadata must match the literal profile `type`. Unsupported
template fragments such as `{{ ... }}`, `{% ... %}`, or `{# ... #}` fail for
referenced connection payloads instead of being passed to adapters.

`recon compile --render-sql` requires `connections/profiles.yml` and loads only
the selected target's connections referenced by compiled contracts. Plain
`recon compile` does not require a profile file.

## `contracts/`

Contracts are the main source files.

They define source-target equivalence.

Recon can parse multiple contract files in a project. Simple multi-contract
YAML files are also supported by parse. Selecting a subset of contracts to
compile or run is a separate future selector feature.

Contract discovery is recursive under configured contract paths, so subfolders
such as `contracts/customer/` and `contracts/orders/` are supported. Generated
compiled contract and check artifacts use the contract name rather than the
source folder, so contract names must be unique across the project.

Future `path:...` selectors should use project-relative manifest paths such as
`contracts/customer/customer_revenue.yml`. Exact file-path selection should come
before directory-prefix selection. Selecting a multi-contract YAML file should
select every contract in that file unless a later selector design explicitly
narrows it further.

## `sample_policies/`

Reusable sampling policies.

## `tolerances/`

Reusable tolerance and normalization policies.

## `schema_policies/`

Reusable schema comparison policies.

Useful for CDC technical columns.

## `target/`

Generated parse/compile/run artifacts.

Do not commit.

Current generated contents can include:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/   # only when recon compile --render-sql succeeds
```

## `reports/`

Generated human-readable evidence.

Do not commit.

## `state/`

Local run state.

Do not commit.
