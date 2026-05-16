# Governance

## Project ownership

Recon Core is maintained by Recon Labs.

Maintainers are responsible for protecting the project direction, repository quality, public contract model, contributor experience, and release integrity.

## Governance principles

Recon Core should remain:

- open-source,
- developer-friendly,
- evidence-driven,
- strict about unsafe reconciliation behavior,
- focused on Reconciliation as Code,
- welcoming to contributors,
- careful with public APIs and contract changes.

## Maintainer responsibilities

Maintainers should:

- review issues and pull requests,
- protect the public contract model,
- keep documentation aligned with implementation,
- require tests for meaningful behavior changes,
- avoid accepting features that weaken trust,
- guide contributors toward small, reviewable changes,
- create or update decision records for durable design choices.

## Decision making

Small implementation decisions can be made in pull requests.

Durable decisions should be captured in `docs/decisions/`.

Durable decisions include changes to:

- contract syntax,
- parse, compile, or run behavior,
- artifact formats,
- validation defaults,
- adapter interfaces,
- package semantics,
- evidence behavior,
- project scope,
- major architecture.

## Contribution expectations

Contributors should follow:

- `CONTRIBUTING.md`,
- `CODE_OF_CONDUCT.md`,
- `SECURITY.md`,
- repository documentation,
- existing decision records.

Pull requests should include tests and documentation when public behavior changes.

## Scope control

Recon Core should remain focused on source-target data equivalence.

The project should avoid drifting into:

- generic data quality,
- ingestion movement,
- CDC movement tooling,
- dashboarding-first workflows,
- MDM or fuzzy entity resolution,
- automatic data repair.

## Maintainer changes

Maintainer roles may expand as the community grows.

Future maintainer additions should be based on sustained, high-quality contributions and alignment with the project principles.

## Release authority

Maintainers control releases, tags, package publication, and compatibility decisions.

Release decisions should follow the release plan and changelog practices documented in the repository.
