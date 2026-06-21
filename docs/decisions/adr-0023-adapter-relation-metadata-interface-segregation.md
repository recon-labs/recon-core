# ADR 0023: Adapter Relation Metadata Interface Segregation

## Status

Accepted.

## Date

2026-06-21.

## Context

ADR 0020 established the first adapter/profile/rendering boundary with
`BaseAdapter` and `SqlRenderer`. That was sufficient for the first local
DuckDB rendering and execution phases, but the initial `BaseAdapter` shape also
made relation metadata methods required for every adapter implementation.

Current compile, render-SQL, registry, runtime setup, row-count execution, and
bounded local/dev grain-key safety execution need adapter identity, API-version
metadata, connection lifecycle, query execution, capability declarations, and
renderer binding. They do not need general relation metadata fetching.

Forcing every adapter to implement `relation_exists()` and `get_columns()` made
minimal adapters and test fakes carry methods they do not support. The current
DuckDB local development adapter declared column metadata as not implemented
and only needed separate internal catalog probes for bounded local/dev scan
safety, not the public relation metadata API.

## Decision

`BaseAdapter` remains the minimum adapter boundary for:

- adapter identity metadata,
- supported adapter API version,
- connection lifecycle,
- query execution,
- capability declaration.

Relation metadata access is a separate nominal interface:

```text
RelationMetadataAdapter
```

That interface owns:

- `relation_exists(relation)`,
- `get_columns(relation)`.

Future callers that need relation metadata must require both:

- the nominal `RelationMetadataAdapter` interface, and
- the relevant metadata capability, such as `metadata_columns`.

Method presence alone, inherited pre-alpha compatibility shims on
`BaseAdapter`, and metadata capability support alone are not permission to call
metadata methods.

`BaseAdapter` may keep non-abstract compatibility shims for pre-alpha method
lookup. Those shims should raise clear `NotImplementedError` messages and must
not be interpreted as support.

`ADAPTER_API_VERSION` remains `"1"` for this change because the current adapter
API is pre-alpha, no external adapter package or shared adapter test kit has
been released, existing adapters that implement metadata methods remain valid,
and the change relaxes requiredness while preserving method lookup
compatibility. A future removal of the shims, payload or return-type changes,
registry behavior changes, capability semantic changes, or broader stable
external adapter compatibility claims require a separate compatibility review
and may require an adapter API version bump.

## Consequences

Minimal adapters no longer need to implement relation metadata methods when
they do not support metadata.

Metadata-capable adapters have a clear nominal interface that future validation,
debug, all-column expansion, schema policy, or adapter test-kit code can
require explicitly.

DuckDB does not become metadata-capable through method presence. It continues
to declare `metadata_columns` as not implemented until general relation
metadata support is designed and tested.

Current compile, render-SQL, registry, runtime setup, row-count execution,
bounded local/dev grain-key safety execution, generated artifact behavior,
result behavior, evidence behavior, diagnostics, and CLI output remain
unchanged.

Public docs, compatibility docs, and future adapter test-kit expectations must
describe `BaseAdapter`, `RelationMetadataAdapter`, and `SqlRenderer` as
separate responsibilities.

## Alternatives Considered

Leaving relation metadata methods abstract on `BaseAdapter` was rejected
because it forces unused behavior onto adapters and makes not-implemented
stubs look like part of the required base contract.

Removing the old methods from `BaseAdapter` entirely was deferred because it
would break pre-alpha method lookup more sharply than needed for the current
scope.

Using structural method presence was rejected because compatibility shims would
make every base adapter appear metadata-capable.

Using capability support alone was rejected because capabilities describe what
an adapter claims it can do, but they do not prove the required interface is
available or safe to call.
