# Implementation

This directory defines detailed implementation guidance for Recon Core.

The framework docs explain what Recon is. The architecture docs explain the system boundaries. These implementation docs explain how to build the first production-quality core.

## Implementation goals

Recon Core should be implemented as a small, strict, testable framework.

The implementation should prioritize:

- contract-first behavior,
- strong validation,
- explicit compilation,
- readable generated artifacts,
- structured diagnostics,
- adapter isolation,
- evidence generation,
- test-driven development.

## Main implementation areas

```text
CLI services
Project loading
Config models
Parser and manifest
Contract compiler and validator
Check planner
Check engine
Adapter interface
Sampling engine
Tolerance and normalization engine
Schema policy engine
CDC policy handling
Artifact writers
Evidence writers
Result model
Diagnostics
Testing
```

## Implementation order

The recommended first build path is:

```text
1. project config and file loading
2. typed resource models
3. parser and manifest writer
4. contract compiler and compiled artifacts
5. diagnostics and validation rules
6. built-in check registry
7. local/dev adapter
8. check planner and runner
9. result model and artifact writers
10. evidence output
11. examples and CLI polish
```

## Hard rules

The implementation must preserve these rules:

- columns define eligible comparison fields, not checks,
- metrics compile into aggregate checks,
- checks and check packs define execution intent,
- check-pack expansion must be visible,
- no silent all-column comparison,
- no silent no-op check packs,
- row-level checks require `grain.keys`,
- row-level checks require unique source and target keys,
- sampling does not remove uniqueness requirements,
- aggregate checks can run without row-level keys,
- invalid check/column type combinations fail validation,
- random sampling requires persisted keys,
- cross-database hash equality is not assumed,
- schema ignores are explicit,
- CDC behavior is explicit,
- generated artifacts are not source files.
