# Documentation Guide

## Purpose

Recon documentation should help users, contributors, and maintainers understand the framework without reading implementation code.

## Style

Documentation should be:

- clear,
- practical,
- direct,
- example-driven,
- consistent with the contract model,
- free of internal planning labels.

## Avoid

Avoid:

- phase labels,
- draft status sections,
- internal planning notes,
- hidden assumptions,
- unexplained jargon,
- examples that silently rely on unsafe behavior.

## Examples

Examples should use fake names and safe placeholder values.

Do not include:

- real credentials,
- customer data,
- production table names,
- private evidence.

## Docs to update

Update docs when changing:

- contract syntax,
- CLI behavior,
- check behavior,
- check-pack behavior,
- sampling behavior,
- tolerance behavior,
- schema policy behavior,
- CDC behavior,
- artifact paths,
- adapter behavior.

## Principle

Docs are part of the product. If behavior is not documented, users cannot safely rely on it.
