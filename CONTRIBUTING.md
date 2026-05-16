# Contributing

Thank you for considering a contribution to Recon Core.

Recon is an open-source Reconciliation as Code framework. Contributions should help make source-target reconciliation safer, clearer, more repeatable, and more evidence-driven.

## Contribution values

Good contributions should be:

- explicit,
- tested,
- documented,
- safe by default,
- compatible with the contract model,
- aligned with the parse, compile, run workflow.

Recon should prefer clear errors over misleading success.

## Before contributing

Read the relevant docs:

- `docs/product/`
- `docs/framework/`
- `docs/planning/`
- `docs/getting-started/`
- `docs/user-guide/`

For implementation work, also read the implementation docs when present.

## Design principles to preserve

Do not introduce behavior that violates these rules:

- columns define eligible comparison fields, not checks,
- metrics compile into aggregate checks,
- checks and check packs define execution intent,
- no silent all-column comparison,
- no silent no-op check packs,
- check-pack expansion must be visible in compiled artifacts,
- row-level checks require `grain.keys`,
- row-level checks require unique keys,
- sampling does not remove uniqueness requirements,
- aggregate checks can run without row-level keys,
- `grain.keys` are row identity,
- `metrics.group_by` is segmentation,
- invalid check/column type combinations fail validation,
- random sampling must persist keys,
- hash sampling cannot assume cross-database hash equality,
- schema ignores must be explicit,
- CDC mode and delete behavior must be explicit,
- evidence must show scope and assumptions.

## Development workflow

Recommended workflow:

```bash
git checkout -b your-change
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Adjust commands as project tooling is implemented.

## Testing expectations

Non-trivial changes should include tests.

Use test-driven development for:

- parser behavior,
- contract validation,
- compiler expansion,
- check planning,
- sampling resolution,
- tolerance precedence,
- schema policy behavior,
- adapter capability handling,
- result model behavior.

Tests should cover both success and failure cases.

## Documentation expectations

Update docs when behavior changes.

Examples:

- contract syntax changes,
- CLI behavior changes,
- artifact format changes,
- validation rule changes,
- check pack behavior changes,
- adapter capability changes,
- evidence output changes.

Documentation should be written as project documentation, not as implementation notes.

## Pull request expectations

A good pull request includes:

- clear summary,
- motivation,
- tests added or updated,
- docs added or updated,
- known limitations,
- evidence of local validation.

## Commit message style

Use clear, descriptive commit messages.

Examples:

```text
Add contract validation for duplicate grain keys
Document schema ignore policies
Implement metric compilation into aggregate checks
```

## What belongs in Recon Core

Recon Core should own:

- CLI,
- project loading,
- contract parsing,
- contract compilation,
- validation rules,
- result model,
- evidence model,
- base adapter interface,
- built-in core checks and check packs.

## What belongs outside Recon Core

Separate packages should eventually own:

- production database adapters,
- domain-specific check packs,
- external orchestration integrations,
- large example environments,
- Hub metadata.

## Security

Do not commit credentials, connection profiles, secrets, customer data, or real production evidence.

Use examples with fake names, fake data, and safe placeholder credentials.

## Questions

Open an issue when a design decision is unclear.

If a change affects public contract syntax, artifact formats, validation behavior, or adapter interfaces, it may need an ADR before implementation.
