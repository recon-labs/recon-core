# Core Design Hardening Item 17 Prework

## Purpose

This is the prework artifact for final-order item 17: define and narrow public
Python package export barrels.

Item 17 is high-risk because package-level imports can become public Python API
for users, adapter authors, future packages, future adapter test kits, tests,
and integrations. Even in pre-alpha, narrowing an import from
`recon_core.adapters`, `recon_core.check_engine`, `recon_core.compiler`,
`recon_core.parser`, or another package facade can break downstream code without
changing CLI, YAML, artifacts, or runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from runtime
capability semantics, renderer binding, DuckDB renderer decomposition,
check-engine decomposition, compile-service decomposition, profile-loader
decomposition, diagnostic-redaction decomposition, adapter metadata interface
segregation, and monolithic service-test cleanup. Item 17 should remain a
Python import/export policy and compatibility-boundary change only.

## Scope

Item 17 prework covers:

- package `__init__.py` facades under `src/recon_core/`,
- package `__all__` declarations,
- public-looking import paths such as `from recon_core.adapters import ...`,
- current internal imports that use broad package facades,
- optional-adapter eager-import safety,
- adapter API and future adapter test-kit import expectations,
- compatibility docs, changelog assessment, tests, regression-capture routing,
  local-success blindness checks, and Definition of Done for the later
  implementation.

The selected design is conservative: classify the intended public and
compatibility import surface first, preserve existing imports unless a removal
is explicitly proven safe, move internal code toward owner-module imports where
that reduces facade coupling, and add tests/guards before narrowing any
package-level export.

## Non-Goals

Item 17 prework and implementation must not implement:

- external adapter discovery,
- Python entry points,
- a third-party renderer registry,
- adapter package extraction,
- shared adapter-test-kit extraction,
- CLI behavior changes,
- contract YAML changes,
- generated artifact schema changes,
- compiled SQL, run result, evidence, report, failure-detail, state, or sink
  behavior,
- adapter API method shape changes,
- adapter capability semantic changes,
- diagnostic code or message changes,
- broad module moves unrelated to package facades,
- a stable 1.0 public API promise.

Item 17 may classify current pre-alpha imports and mark some compatibility
aliases as intentionally retained. It must not present the whole current
`__all__` surface as stable just because the imports continue to work.

## Current Audit Findings

Current package facades are uneven by design and by history:

- `src/recon_core/__init__.py` is intentionally small and exports only
  `__version__` and `get_version`.
- `src/recon_core/diagnostics/__init__.py`,
  `src/recon_core/config/__init__.py`,
  `src/recon_core/project/__init__.py`, and
  `src/recon_core/services/__init__.py` are relatively small convenience
  facades.
- `src/recon_core/adapters/__init__.py` exports adapter interfaces, capability
  models, registry types, rendering helpers, runtime setup helpers, diagnostic
  constants, `ConnectionConfig`, and a lazy `default_adapter_registry()` helper.
  It currently avoids importing `recon_core.adapters.duckdb` eagerly.
- `src/recon_core/adapters/duckdb/__init__.py` intentionally owns concrete
  DuckDB adapter and renderer exports.
- `src/recon_core/check_engine/__init__.py` exports result models, engine
  classes, dispatch constants, row-count execution helpers, and execution
  support constants.
- `src/recon_core/compiler/__init__.py` exports a broad compiler model,
  validation, check-pack, metric, policy, ID, and diagnostic-constant surface.
- `src/recon_core/parser/__init__.py` exports authored model, manifest, resource
  discovery, YAML loader, and parser diagnostics surfaces.
- `src/recon_core/artifacts/__init__.py` exports current artifact writers,
  loaders, loaded artifact models, artifact names, and diagnostics constants.
- `src/recon_core/profiles/__init__.py` exports connection models, selected
  profile loading, referenced-connection helpers, and profile diagnostics
  constants.

Audit count from current code:

| Package facade | Current `__all__` count | Current interpretation |
| --- | ---: | --- |
| `recon_core` | 2 | Root version-only package surface. |
| `recon_core.adapters` | 35 | Adapter API, capability, registry, rendering, runtime setup, and compatibility convenience surface. |
| `recon_core.adapters.duckdb` | 8 | In-core DuckDB adapter convenience surface. |
| `recon_core.check_engine` | 26 | Current in-memory check-engine result/execution convenience surface. |
| `recon_core.compiler` | 97 | Broad compiler/model/diagnostic convenience surface. |
| `recon_core.parser` | 37 | Broad parser/model/resource/YAML convenience surface. |
| `recon_core.artifacts` | 24 | Artifact writer/loader/model convenience surface. |
| `recon_core.profiles` | 15 | Profile loader/model/diagnostic convenience surface. |
| `recon_core.services` | 7 | Service facade used by CLI and tests. |
| `recon_core.config` | 5 | Project-config facade. |
| `recon_core.project` | 8 | Project context/path facade. |
| `recon_core.diagnostics` | 3 | Structured diagnostic model facade. |
| `recon_core.cli` | 1 | CLI entrypoint facade. |

Current docs already say the `recon-core` package is `0.0.0` and pre-alpha with
no stable public API guarantee. They also treat adapter API, diagnostics,
artifacts, typed plans, result-like models, package behavior, and cross-repo
compatibility as public contract surfaces that require explicit compatibility
review when changed.

Current source and tests import from facades heavily. That means a package
export cleanup must distinguish:

- imports that are intentional public or adapter-facing conveniences,
- imports that are compatibility aliases for existing pre-alpha users/tests,
- imports that internal code can move to owner modules without breaking
  external import paths,
- exports that should not be added again because they make internal helpers look
  public.

## Export Policy Decision

Item 17 should classify package-level exports into four support categories.

### Public framework surface

Names in this category are documented user, adapter-author, package-author, or
integration surfaces. They may still be pre-alpha, but changes need public
contract review, compatibility docs, tests, changelog assessment, and migration
or deprecation guidance when breaking.

Examples likely to stay in this category:

- root version helpers,
- `Diagnostic`, `DiagnosticSeverity`, and public diagnostic dict shape,
- adapter interfaces and adapter model primitives that external adapter authors
  need,
- service classes that CLI code and simple Python embedding currently use, if
  the project chooses to keep service embedding public.

### Adapter/test-kit-facing pre-alpha surface

Names in this category are public-ish because future adapter packages and the
shared adapter test kit may import them, but they are still governed by the
pre-alpha adapter API and compatibility matrix. Changes require adapter API and
test-kit impact review.

Examples likely to stay in this category:

- `BaseAdapter`,
- `RelationMetadataAdapter`,
- `SqlRenderer`,
- `AdapterCapabilities`,
- `CapabilitySupport`,
- `ADAPTER_API_VERSION`,
- adapter registry/factory types and adapter API compatibility helpers,
- renderer models that the adapter test kit may need.

### Compatibility convenience re-export

Names in this category remain import-compatible for current pre-alpha users,
tests, or internal code, but they are not promoted as durable public API. They
should be documented as compatibility aliases or left undocumented until the
stable API policy is ready.

Examples to review carefully:

- broad compiler and parser dataclasses from `recon_core.compiler` and
  `recon_core.parser`,
- check-engine execution helpers from `recon_core.check_engine`,
- artifact loaded-model aliases from `recon_core.artifacts`,
- profile helper aliases from `recon_core.profiles`,
- diagnostic constants that are useful for tests but not intended as stable
  import API.

### Internal-only implementation detail

Names in this category should not be exported from package facades. New private
helpers, split modules, default registries, default renderer maps, concrete
runtime safety wiring, and policy internals should be imported from owner
modules by internal code.

Examples:

- helpers with leading-underscore modules,
- default-renderer wiring helpers,
- concrete scan-safety mechanics,
- low-level diagnostic-redaction token/matching helpers,
- local orchestration helpers owned by service modules.

## Narrowing Rules

Implementation must follow these rules before removing an export:

1. Identify whether the name is documented, tested through a facade import, used
   by another package facade, or plausibly adapter/test-kit-facing.
2. If it is adapter API, typed-plan, artifact, diagnostic, service, or result
   shaped, treat removal as a public contract risk even before 1.0.
3. Prefer moving internal imports to owner modules first while preserving
   package-level aliases.
4. Do not remove compatibility aliases when the only benefit is internal
   cleanliness.
5. Remove or stop exporting a name only when it is clearly an internal helper,
   not documented, not needed by adapter/test-kit-facing code, and covered by
   tests plus compatibility/changelog review.
6. Do not add new facade exports for helpers introduced by this branch unless
   the prework or compatibility docs classify them as public or adapter-facing.
7. Do not make package imports load concrete optional adapters unless importing
   the concrete adapter package itself, such as `recon_core.adapters.duckdb`.

## Expected Implementation Shape

The later item 17 implementation should be narrow and staged:

1. Add or update compatibility documentation for the Python import surface.
   Preferred target: add a `Python package import surface` row to
   `docs/compatibility/public-contract-inventory.md` and expand the
   `recon-core package` row in `docs/compatibility/compatibility-matrix.md`.
2. Add focused import-surface tests before changing exports:
   - current public/adapter-facing imports still resolve,
   - package `__all__` contains only classified names,
   - `import recon_core.adapters` does not import `recon_core.adapters.duckdb`,
   - `default_adapter_registry()` remains lazy and does not make the adapter
     facade itself load concrete adapters,
   - concrete DuckDB imports remain available from
     `recon_core.adapters.duckdb`.
3. Move internal code away from broad facades where the owner module is clearer
   and where the move does not change public import compatibility.
4. Narrow only clearly internal facade exports that were accidental. If a name
   is uncertain, keep it as a compatibility alias and record why.
5. Update regression-capture routing for any new export-policy test file or
   newly owned `__init__.py` surface, rather than relying on broad prefixes
   accidentally.
6. Run the local-success blindness second pass before calling the item complete.

Exact test file names may be decided during implementation. If a new path such
as `tests/compatibility/test_python_package_exports.py` is introduced, it must
be exact-routed in `docs/compatibility/regression-capture/index.yml` before the
branch relies on the advisory decision check.

## Responsibility Map

| Module or component | Allowed responsibility | Forbidden responsibility | Boundary tests |
| --- | --- | --- | --- |
| Root `recon_core.__init__` | Version-only package identity. | Importing services, adapters, parser, compiler, diagnostics, or concrete optional dependencies. | Import root package and assert minimal `__all__`. |
| Neutral package facades | Intentional public, adapter-facing, or compatibility re-exports. | Exporting newly split private helpers by default; eager concrete adapter imports; changing behavior while cleaning imports. | `__all__` allowlist/classification tests and import compatibility tests. |
| `recon_core.adapters.__init__` | Adapter API primitives, capability/registry/rendering model surface, compatibility aliases, lazy default registry helper. | Eager DuckDB or future connector imports; default renderer exports; scan-safety mechanics; private redaction internals. | Import facade without DuckDB modules in `sys.modules`; adapter-facing import tests. |
| `recon_core.adapters.duckdb.__init__` | Concrete in-core DuckDB adapter, factory, renderer, and DuckDB lifecycle diagnostics. | Becoming the generic adapter registry, renderer registry, or external package discovery point. | Concrete package import test, optional dependency behavior checks when applicable. |
| Owner modules | Define behavior, dataclasses, constants, validation helpers, and implementation details. | Relying on facade imports when that creates cycles, optional dependency coupling, or ambiguous ownership. | Static import guards and focused module tests. |
| Public compatibility docs | Classify import support level and compatibility review rules. | Claiming stable 1.0 Python API support before release policy says so. | Docs review plus public research-attribution scan. |
| Regression-capture metadata | Route new export-policy tests and changed `__init__.py` surfaces to the right carryover gates. | Letting new public API tests or package barrels be invisible to advisory checks. | `check_regression_capture.py` and decision advisory tests when routing changes. |

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Root package import | `import recon_core` exposes version helpers only and does not load broad subsystems. | Import-surface test. |
| Neutral adapter facade import | `import recon_core.adapters` does not import `recon_core.adapters.duckdb` or any future concrete adapter package. | Import-surface test inspecting loaded modules. |
| Adapter API imports | Current adapter-facing imports such as `BaseAdapter`, `RelationMetadataAdapter`, `SqlRenderer`, `ADAPTER_API_VERSION`, capability models, and registry types remain available unless a compatibility review explicitly changes them. | Import compatibility tests and docs mapping. |
| Concrete DuckDB imports | DuckDB adapter, factory, and renderer remain importable from `recon_core.adapters.duckdb`. | Import compatibility test. |
| Default registry laziness | The adapter facade keeps `default_adapter_registry()` lazy so importing the facade itself does not load concrete adapters. | Import-surface test; optionally call helper in a test that expects DuckDB registration only after invocation. |
| No helper leak | New private helper modules from prior hardening items are not added to package `__all__` unless classified as public. | `__all__` allowlist or denylist test. |
| Internal imports | Internal modules import owner modules where broad facades create optional dependency, cycle, or public-API ambiguity. | Static grep/AST guard for selected high-risk paths. |
| Compatibility aliases | Existing broad compiler/parser/check-engine/artifact/profile imports are kept unless the implementation proves removal is safe and documents the compatibility decision. | Existing tests plus explicit import-surface tests for retained aliases. |
| Public docs alignment | Compatibility docs state that the Python import surface is pre-alpha, classified, and compatibility-reviewed before breaking changes. | Docs update review and public attribution scan. |
| Changelog decision | Export removal or support-level change gets changelog review; docs/tests-only classification may be Not Required. | Final changelog decision recorded. |
| Regression-capture routing | New export-policy test paths and changed package barrels are routed to relevant surfaces/gates. | `check_regression_capture.py` plus advisory decision check. |
| Runtime behavior unchanged | CLI, YAML parsing, compile, render-SQL, run, artifacts, diagnostics, results, and evidence behavior are unchanged. | Focused existing tests plus full validation. |

## BDD-Style Import Scenarios

Scenario: adapter author imports the minimum adapter interface.

- Given an adapter author imports `BaseAdapter`, `RelationMetadataAdapter`,
  `SqlRenderer`, and `ADAPTER_API_VERSION` from `recon_core.adapters`,
- when the item 17 implementation is installed,
- then those imports still resolve unless a documented compatibility decision
  explicitly removes them.

Scenario: neutral adapter facade import is side-effect light.

- Given a Python process imports `recon_core.adapters`,
- when no concrete adapter package is requested,
- then `recon_core.adapters.duckdb` is not imported as a side effect.

Scenario: concrete DuckDB package owns concrete DuckDB exports.

- Given code imports `DuckDbAdapter`, `DuckDbAdapterFactory`, or
  `DuckDbSqlRenderer`,
- when the import path is `recon_core.adapters.duckdb`,
- then the concrete package owns that import and may load DuckDB-specific
  modules.

Scenario: internal code stops depending on facades for ownership convenience.

- Given a service or check-engine module needs a concrete model/helper,
- when the owner module is unambiguous and importing it does not create a cycle,
- then the module should import from the owner module instead of treating the
  facade as an internal dependency hub.

## Public Contract Impact

Affected public contract surfaces:

- `recon-core` Python package import surface,
- adapter API imports and adapter API compatibility,
- future adapter test-kit imports,
- cross-repo compatibility expectations,
- possibly check-engine, compiler, parser, artifacts, profiles, and services
  Python embedding surfaces.

Current status remains pre-alpha. Item 17 should not claim stable 1.0 Python API
support. It should make the pre-alpha support levels explicit so future agents
do not accidentally broaden or narrow imports without review.

ADR impact:

- A new ADR is not required for a compatibility-preserving classification and
  test/guard implementation.
- A new ADR or ADR update may be required if item 17 removes broad exports,
  changes adapter API imports, changes service embedding expectations, or
  defines durable post-1.0 Python API policy.

Compatibility docs likely needing updates during implementation:

- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- possibly `docs/compatibility/adapter-api.md` if adapter-facing import paths
  are narrowed or classified more strictly.

Changelog impact:

- Prework only: Not Required.
- Docs/tests-only classification with no import break: likely Not Required.
- Removing or renaming an import path, changing adapter-facing export support,
  or changing a documented Python embedding surface: likely `Changed` under
  `Unreleased`.

## Regression-Capture Review

Matching carryover gates checked:

- `adapter_testkit_regression_carryover` for adapter API, adapter capability,
  SQL rendering, and cross-repo adapter compatibility surfaces.
- `check_engine_semantics_carryover` if check-engine package exports are
  narrowed or reclassified in a way that affects result/execution consumers.
- `parser_compiler_contract_carryover` if compiler/parser package exports or
  typed-plan-facing imports are narrowed.
- `artifact_publication_carryover` only if artifact writer/loader exports
  change in a way that affects generated artifact publication or readers.

Prework `regression_capture_decision`: not-required.

Rationale:

- This prework adds a planning artifact only.
- No runtime behavior, tests, capture metadata, public imports, artifacts,
  diagnostics, or compatibility promises are changed by the prework itself.

Implementation must re-evaluate this decision. If it adds export-policy tests,
changes package facades, changes compatibility docs, or creates new owned
surfaces, it must update routing metadata or record an explicit no-capture
rationale. Do not rely only on broad prefixes:

- `src/recon_core/adapters/`, `tests/adapters/`,
  `src/recon_core/check_engine/`, `tests/check_engine/`,
  `src/recon_core/artifacts/`, and `tests/artifacts/` currently have broad
  routing.
- package facades under `compiler`, `parser`, `profiles`, `config`, `project`,
  and `services` may need exact routing if item 17 changes them.
- any new `tests/compatibility/` or `tests/public_api/` path must be added to
  `docs/compatibility/regression-capture/index.yml`.

## Security And Privacy Impact

Item 17 should not touch credentials, profiles, rendered profile values,
runtime query text, source/target data, generated evidence, or debug artifacts.

Security/privacy risks are indirect:

- eager imports can load optional database packages earlier than intended,
- broad facades can make private diagnostic or runtime helpers appear safe for
  third-party use,
- import cleanup can hide a change to adapter diagnostic constants or redaction
  helpers if tests only check local runtime behavior.

The implementation must preserve current diagnostic redaction, profile handling,
and source/target privacy behavior.

## Local-Success Blindness Second Pass

Passing local import tests is insufficient if the implementation still:

- removes a public-looking import without compatibility review,
- treats undocumented current imports as stable without classifying them,
- makes `recon_core.adapters` load `recon_core.adapters.duckdb` or future
  concrete adapters during neutral facade import,
- adds new helper exports because a local test imported from a package facade,
- rewrites internal imports to broad facades where owner modules are clearer,
- breaks existing adapter-facing imports while local DuckDB tests still pass,
- claims no public contract impact because CLI/YAML/artifact behavior is
  unchanged,
- adds new export-policy tests under paths invisible to regression-capture
  routing,
- hides an import break by updating only local tests.

Required second-pass checks after implementation:

```bash
python3 -m pytest tests/...focused item 17 tests... -q
python3 -m pytest tests/services/test_compile_service.py tests/services/test_run_service.py tests/check_engine/test_engine.py tests/adapters/test_registry.py tests/adapters/test_runtime_setup.py -q
python3 scripts/check_regression_capture.py
python3 scripts/check_regression_capture_decisions.py --base-ref origin/main
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy src
python3 -m compileall -q src tests
python3 -m pytest -q
git diff --check
```

Suggested static guards:

```bash
python3 -c 'import sys; import recon_core.adapters; assert "recon_core.adapters.duckdb" not in sys.modules'
rg -n "default_runtime_renderers_by_adapter_type" src/recon_core/adapters/__init__.py
rg -n "from recon_core\\.adapters import .*DuckDb|recon_core\\.adapters\\.duckdb" src/recon_core/check_engine src/recon_core/services/run.py
```

The exact focused test paths should be adjusted to the implementation.

## Definition Of Done

Item 17 implementation is done only when:

- package export support categories are documented,
- current intended public/adapter-facing imports are protected by tests,
- neutral package imports remain side-effect light,
- optional concrete adapter imports are not introduced through neutral facades,
- internal imports use owner modules where needed to reduce facade coupling,
- any narrowed export has explicit compatibility, changelog, and migration or
  no-migration reasoning,
- regression-capture routing covers new export-policy test/doc surfaces or a
  no-capture rationale is recorded,
- local-success blindness second pass is complete,
- full validation passes.

## Future Implementation Plan

1. Read this prework plus:
   - `docs/compatibility/public-contract-inventory.md`,
   - `docs/compatibility/compatibility-matrix.md`,
   - `docs/compatibility/adapter-api.md`,
   - `docs/architecture/adapter-interface.md`,
   - `docs/implementation/adapter-interface-spec.md`,
   - `docs/framework/repository-strategy.md`,
   - `docs/compatibility/regression-capture/index.yml`.
2. Add compatibility docs for the pre-alpha Python import surface and support
   categories.
3. Add focused import-surface tests and static guards.
4. Move internal facade imports to owner-module imports only where the move is
   clearly behavior-preserving and reduces optional dependency or ownership
   ambiguity.
5. Narrow only clearly internal exports. Keep uncertain names as compatibility
   aliases.
6. Update regression-capture routing for any new test path or newly owned
   facade surface.
7. Run focused tests, regression-capture validators, full validation, and the
   local-success blindness second pass.

Recommended implementation commit message:

```text
refactor: classify and guard package export surfaces
```
