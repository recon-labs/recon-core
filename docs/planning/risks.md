# Risks

## Purpose

This document captures product, technical, and adoption risks for Recon.

The goal is to make risks explicit so the framework can be designed carefully.

## Product risks

### Too broad

Recon could drift into generic data quality, observability, ingestion, MDM, or dashboarding.

Mitigation:

- keep source-target equivalence as the core,
- keep non-goals visible,
- reject features that do not strengthen contracts, checks, sampling, evidence, or adapters.

### Too narrow

Recon could become only a table diff script.

Mitigation:

- build contracts, check packs, policies, compiled artifacts, state, evidence, and packages,
- make the framework more than raw diff execution.

### Confusing mental model

Users may confuse columns, metrics, checks, and sampling.

Mitigation:

- keep docs clear,
- compile behavior into visible artifacts,
- provide examples for common patterns,
- produce actionable validation errors.

### Hidden behavior

Check packs and defaults could hide what actually runs.

Mitigation:

- compile check packs into explicit checks,
- show sampling, tolerance, schema ignores, CDC mode, and null rules in artifacts,
- avoid silent all-column comparison.

## Technical risks

### Cross-database differences

Different systems handle SQL, types, timestamps, identifiers, nulls, empty strings, precision, and hashing differently.

Mitigation:

- use adapters,
- require capability declarations,
- avoid assuming portable hashes,
- validate compatibility before execution when possible.

### Row matching ambiguity

Null or duplicate keys make row-level comparison unreliable.

Mitigation:

- require `grain.keys` for row-level checks,
- validate uniqueness,
- block row-level checks when keys are null or duplicated.

### CDC identity ambiguity

CDC update and delete propagation may depend on source primary keys, unique
keys, or event keys that differ from comparison grain.

Mitigation:

- model CDC identity with explicit `cdc.keys`,
- allow `same_as: grain` only when declared,
- require delete behavior and ordering configuration for CDC checks that need them.

### Sampling mistakes

Sampling can create misleading evidence if source and target samples differ or if reports imply full validation.

Mitigation:

- persist random sample keys,
- make sampling scope visible,
- require explicit full versus sampled evidence,
- do not assume cross-database hash equality.

### CDC complexity

CDC has many patterns: upserts, append-only logs, hard deletes, soft deletes, operation columns, tombstones, late data, and SCD2 history.

Mitigation:

- require explicit CDC mode,
- require explicit CDC keys where propagation checks need change identity,
- design CDC check packs as configurable,
- start with a small supported subset,
- document unsupported modes clearly.

### Schema drift and technical columns

Ingestion and CDC tools add technical columns that can break schema checks or hide drift if ignored too broadly.

Mitigation:

- schema checks strict by default,
- explicit ignore lists and patterns,
- source/target-specific ignores,
- evidence showing ignored columns.

### Sensitive data in evidence

Failure details may expose PII or confidential values.

Mitigation:

- row limits,
- optional failure export,
- masking/redaction later,
- clear evidence configuration.

## Adoption risks

### Existing tools cover enough

Some teams may already use dataset-local tests, data quality tools, migration
validation CLIs, data diff tools, or custom scripts.

Mitigation:

- position Recon narrowly around Reconciliation as Code,
- focus on source-target equivalence,
- make the open-source developer workflow excellent.

### Setup friction

If the project model is too complex, users may prefer scripts.

Mitigation:

- provide a simple quickstart,
- support relation-first compare views,
- make `recon init` helpful,
- keep MVP contract syntax small.

### Adapter availability

Users may need databases not supported early.

Mitigation:

- design adapter interface early,
- define typed check plans and adapter API versioning before many adapters,
- ship at least one practical local adapter,
- create adapter test kit after typed plan and adapter API stabilize,
- invite community adapters.

### Trust

Users will not trust a reconciliation tool that produces surprising results.

Mitigation:

- strict validation,
- explicit compiled plan,
- clear warnings/errors,
- evidence-rich output.

## Execution risks

### Overengineering

Building packages, Hub, cloud, and many adapters too early could slow progress.

Mitigation:

- build the core loop first,
- split repos only when stable,
- prioritize end-to-end usefulness.

### Under-documenting decisions

If decisions are not written down, coding agents and contributors may drift.

Mitigation:

- keep framework docs current,
- add ADRs for durable decisions,
- keep implementation docs aligned with behavior.

## Risk principle

The biggest risk is not failing a check.

The biggest risk is producing evidence that looks trustworthy while the comparison was unsafe.

Recon should prefer clear errors over misleading success.
