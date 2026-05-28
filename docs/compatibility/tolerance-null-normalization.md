# Tolerance, Null, And Normalization Compatibility

## Purpose

Tolerance, null, and normalization policies affect whether Recon considers
source and target values equivalent.

These policies are compatibility surfaces because users, adapters, generated
artifact readers, result consumers, and evidence reports may depend on the
resolved comparison semantics.

## Current Status

ADR 0009 locks the design.

Current implementation status:

- numeric tolerance may be preserved in current compiled checks for existing
  metric behavior,
- contracts accept a named `tolerance_policy` reference and contract-level
  `nulls`,
- contracts do not accept a top-level `normalization` field,
- compiled contracts currently emit `policies.tolerance_policy`; compiled
  artifact policy visibility is additive and must preserve existing field
  meanings,
- the full typed policy resolver is not implemented yet,
- row-level value checks are not implemented yet,
- reusable tolerance policy resource loading is not implemented yet,
- adapter execution and evidence rendering are not implemented yet.

## Compatibility Rules

These changes require compatibility review:

- accepting a new authored tolerance, null, or normalization YAML shape,
- changing default null behavior,
- changing policy precedence,
- changing resolved policy fields in compiled artifacts,
- changing typed check-plan policy payloads,
- changing adapter capabilities required for policy execution,
- changing run result or failure-detail fields for raw, normalized, or diff
  values,
- changing evidence/report interpretation of tolerated or normalized matches,
- adding reusable tolerance policy resource schema or package support.

Unsupported future policy config must fail validation when Recon can see it. It
must not be silently ignored.

## Locked MVP Policy Surface

MVP policy behavior:

- numeric absolute tolerance only,
- explicit string-like null sentinels by literal value and limited regex,
- explicit ordered string normalization steps,
- limited regex replacement normalization,
- strict defaults,
- resolved policy visibility before execution evidence is trusted.

Future behavior:

- relative tolerance,
- percentage tolerance,
- timestamp tolerance execution,
- locale-aware string handling,
- unrestricted regex features,
- custom SQL or macro normalization,
- reusable policy files,
- project-level default policy files.

## Artifact Expectations

Compiled checks that use policy behavior should show resolved policy fields:

```yaml
tolerance:
  type: absolute
  value: 0.01
nulls:
  treat_as_null:
    values: []
    regex: []
normalization:
  steps: []
```

Typed plans must carry structured resolved policy data or reference resolved
compiled-check policy data. Raw authored strings such as `5 seconds` or
`trim_lower` must not be typed operation payloads. Regex normalization must
appear as typed steps with explicit pattern and replacement fields.

Run results and evidence should show resolved policies when they affect a
check, and should distinguish raw and normalized values when evidence policy
allows value capture. If a string value becomes null because of
`nulls.treat_as_null`, generated evidence should identify the literal sentinel
or regex rule when evidence policy allows that detail.

## Diagnostics

Policy diagnostics are locked by ADR 0009 and follow ADR 0016 phase ownership.

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_VALIDATE_INVALID_TOLERANCE` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_POLICY` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_SENTINEL` | compile validation | error |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_INVALID_REGEX_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error |
| `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` | compile or adapter metadata validation | error |
| `RC_VALIDATE_METADATA_VALIDATION_DEFERRED` | adapter metadata validation | warning |

## Related Docs

- `docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`
- `docs/framework/tolerance-policies.md`
- `docs/implementation/tolerance-and-normalization-engine.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/implementation/result-model.md`
- `docs/framework/evidence.md`
