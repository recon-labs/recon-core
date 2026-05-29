"""Sampling and comparison policy validation for compiler-owned behavior."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TypeAlias

from recon_core.compiler.models import ResolvedSampling
from recon_core.compiler.validation import CompilerDiagnosticContext
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_SAMPLING = "RC_VALIDATE_INVALID_SAMPLING"
INVALID_TOLERANCE = "RC_VALIDATE_INVALID_TOLERANCE"
INVALID_NULL_POLICY = "RC_VALIDATE_INVALID_NULL_POLICY"
INVALID_NULL_SENTINEL = "RC_VALIDATE_INVALID_NULL_SENTINEL"
INVALID_NORMALIZATION = "RC_VALIDATE_INVALID_NORMALIZATION"
INVALID_REGEX_NORMALIZATION = "RC_VALIDATE_INVALID_REGEX_NORMALIZATION"

_SIMPLE_NORMALIZATION_STEPS = frozenset({"trim", "collapse_whitespace", "lower", "upper"})
_REGEX_REPLACE_FIELD = "regex_replace"
_UNSUPPORTED_REGEX_TOKENS = (
    "(?=",
    "(?!",
    "(?<=",
    "(?<!",
    "(?P<",
    "(?P=",
    "(?i",
    "(?m",
    "(?s",
    "(?x",
    "(?a",
    "(?L",
    "(?u",
)
_NormalizationStep: TypeAlias = str | tuple[str, str]


@dataclass(frozen=True, slots=True)
class PolicyValidationResult:
    """Validation diagnostics for one policy family."""

    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class SamplingValidationResult:
    """Resolved current sampling metadata plus validation diagnostics."""

    sampling: ResolvedSampling
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


def validate_sampling(
    sampling: Mapping[str, object] | None,
    *,
    context: CompilerDiagnosticContext | None = None,
) -> SamplingValidationResult:
    """Validate current contract-level sampling shape."""
    resolved_sampling = ResolvedSampling()
    diagnostic_context = context or CompilerDiagnosticContext(resource_type="contract")
    if sampling is None:
        return SamplingValidationResult(sampling=resolved_sampling)

    unsupported_fields = sorted(set(sampling) - {"default_policy"})
    if unsupported_fields:
        return SamplingValidationResult(
            sampling=resolved_sampling,
            diagnostics=(
                _sampling_diagnostic(
                    diagnostic_context,
                    f"Unsupported `sampling` fields: {', '.join(unsupported_fields)}.",
                ),
            ),
        )

    if "default_policy" not in sampling:
        return SamplingValidationResult(
            sampling=resolved_sampling,
            diagnostics=(
                _sampling_diagnostic(
                    diagnostic_context,
                    "Contract `sampling` requires `default_policy` when declared.",
                ),
            ),
        )

    default_policy = sampling["default_policy"]
    if default_policy == "full":
        return SamplingValidationResult(sampling=resolved_sampling)
    if not isinstance(default_policy, str) or not default_policy:
        return SamplingValidationResult(
            sampling=resolved_sampling,
            diagnostics=(
                _sampling_diagnostic(
                    diagnostic_context,
                    "Contract `sampling.default_policy` must be `full` or a non-empty string.",
                ),
            ),
        )
    return SamplingValidationResult(sampling=ResolvedSampling(mode=None, policy=default_policy))


def validate_tolerance(
    tolerance: object,
    *,
    resource_type: str | None,
    resource_name: str | None,
) -> PolicyValidationResult:
    """Validate MVP numeric absolute tolerance shape."""
    context = CompilerDiagnosticContext(resource_type=resource_type, resource_name=resource_name)
    if _decimal_from_number(tolerance) is not None:
        return PolicyValidationResult()

    if isinstance(tolerance, Mapping):
        unknown_fields = sorted(set(tolerance) - {"type", "value"})
        tolerance_type = tolerance.get("type")
        tolerance_value = tolerance.get("value")
        if (
            not unknown_fields
            and tolerance_type == "absolute"
            and _decimal_from_number(tolerance_value) is not None
        ):
            return PolicyValidationResult()

    return PolicyValidationResult(
        diagnostics=(
            context.error(
                code=INVALID_TOLERANCE,
                message=(
                    "Tolerance must be a finite non-negative number or an object with "
                    "`type: absolute` and a finite non-negative `value`."
                ),
                hint="Use `tolerance: 0.01` or `tolerance: {type: absolute, value: 0.01}`.",
            ),
        )
    )


def validate_null_policy(
    nulls: object,
    *,
    resource_type: str | None,
    resource_name: str | None,
    context: CompilerDiagnosticContext | None = None,
) -> PolicyValidationResult:
    """Validate supported null sentinel policy shape."""
    diagnostic_context = context or CompilerDiagnosticContext(
        resource_type=resource_type,
        resource_name=resource_name,
    )
    if not isinstance(nulls, Mapping):
        return PolicyValidationResult(
            diagnostics=(
                _null_policy_diagnostic(
                    diagnostic_context,
                    "Null policy must be a mapping.",
                ),
            )
        )

    unknown_fields = sorted(set(nulls) - {"treat_as_null"})
    if unknown_fields:
        return PolicyValidationResult(
            diagnostics=(
                _null_policy_diagnostic(
                    diagnostic_context,
                    f"Null policy has unsupported fields: {', '.join(unknown_fields)}.",
                ),
            )
        )

    treat_as_null = nulls.get("treat_as_null", {})
    if not isinstance(treat_as_null, Mapping):
        return PolicyValidationResult(
            diagnostics=(
                _null_policy_diagnostic(
                    diagnostic_context,
                    "`nulls.treat_as_null` must be a mapping.",
                ),
            )
        )

    unknown_treat_fields = sorted(set(treat_as_null) - {"values", "regex"})
    if unknown_treat_fields:
        return PolicyValidationResult(
            diagnostics=(
                _null_policy_diagnostic(
                    diagnostic_context,
                    (
                        "`nulls.treat_as_null` has unsupported fields: "
                        f"{', '.join(unknown_treat_fields)}."
                    ),
                ),
            )
        )

    diagnostics: list[Diagnostic] = []
    values = treat_as_null.get("values", ())
    regex_patterns = treat_as_null.get("regex", ())

    if not isinstance(values, Sequence) or isinstance(values, str):
        diagnostics.append(
            _null_sentinel_diagnostic(
                diagnostic_context,
                "`nulls.treat_as_null.values` must be a list of strings.",
            )
        )
    elif not all(isinstance(value, str) for value in values):
        diagnostics.append(
            _null_sentinel_diagnostic(
                diagnostic_context,
                "`nulls.treat_as_null.values` entries must be strings.",
            )
        )
    elif len(set(values)) != len(values):
        diagnostics.append(
            _null_sentinel_diagnostic(
                diagnostic_context,
                "`nulls.treat_as_null.values` entries must be unique.",
            )
        )

    if not isinstance(regex_patterns, Sequence) or isinstance(regex_patterns, str):
        diagnostics.append(
            _null_sentinel_diagnostic(
                diagnostic_context,
                "`nulls.treat_as_null.regex` must be a list of regex strings.",
            )
        )
    elif not all(isinstance(pattern, str) for pattern in regex_patterns):
        diagnostics.append(
            _null_sentinel_diagnostic(
                diagnostic_context,
                "`nulls.treat_as_null.regex` entries must be strings.",
            )
        )
    else:
        diagnostics.extend(
            diagnostic
            for diagnostic in (
                _regex_diagnostic(diagnostic_context, pattern) for pattern in regex_patterns
            )
            if diagnostic is not None
        )

    return PolicyValidationResult(diagnostics=tuple(diagnostics))


def validate_normalized_null_sentinels(
    nulls: object,
    normalization: object,
    *,
    resource_type: str | None,
    resource_name: str | None,
) -> PolicyValidationResult:
    """Validate literal null sentinel uniqueness after string normalization."""
    values = _literal_null_values(nulls)
    steps = _normalization_steps(normalization)
    if values is None or steps is None:
        return PolicyValidationResult()

    seen_values: dict[str, str] = {}
    for value in values:
        normalized_value = _apply_normalization_steps(value, steps)
        existing_value = seen_values.get(normalized_value)
        if existing_value is not None:
            context = CompilerDiagnosticContext(
                resource_type=resource_type,
                resource_name=resource_name,
            )
            return PolicyValidationResult(
                diagnostics=(
                    _null_sentinel_diagnostic(
                        context,
                        "Null sentinel values must remain unique after normalization.",
                    ),
                )
            )
        seen_values[normalized_value] = value

    return PolicyValidationResult()


def validate_normalization(
    normalization: object,
    *,
    resource_type: str | None,
    resource_name: str | None,
) -> PolicyValidationResult:
    """Validate supported string normalization shape."""
    context = CompilerDiagnosticContext(resource_type=resource_type, resource_name=resource_name)
    if not isinstance(normalization, Mapping):
        return PolicyValidationResult(
            diagnostics=(
                _normalization_diagnostic(context, "Normalization policy must be a mapping."),
            )
        )

    unknown_fields = sorted(set(normalization) - {"steps"})
    if unknown_fields:
        return PolicyValidationResult(
            diagnostics=(
                _normalization_diagnostic(
                    context,
                    f"Normalization policy has unsupported fields: {', '.join(unknown_fields)}.",
                ),
            )
        )

    steps = normalization.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, str):
        return PolicyValidationResult(
            diagnostics=(
                _normalization_diagnostic(
                    context,
                    "`normalization.steps` must be a list.",
                ),
            )
        )

    diagnostics: list[Diagnostic] = []
    simple_steps: set[str] = set()
    for step in steps:
        if isinstance(step, str):
            if step not in _SIMPLE_NORMALIZATION_STEPS:
                diagnostics.append(
                    _normalization_diagnostic(
                        context,
                        f"Unsupported normalization step: {step}.",
                    )
                )
                continue
            if step in simple_steps:
                diagnostics.append(
                    _normalization_diagnostic(
                        context,
                        f"Normalization step `{step}` is declared more than once.",
                    )
                )
                continue
            simple_steps.add(step)
            continue

        if isinstance(step, Mapping):
            diagnostics.extend(_validate_regex_replace_step(context, step))
            continue

        diagnostics.append(
            _normalization_diagnostic(
                context,
                "Normalization steps must be strings or `regex_replace` mappings.",
            )
        )

    if "lower" in simple_steps and "upper" in simple_steps:
        diagnostics.append(
            _normalization_diagnostic(
                context,
                "Normalization steps `lower` and `upper` cannot both be used.",
            )
        )

    return PolicyValidationResult(diagnostics=tuple(diagnostics))


def _validate_regex_replace_step(
    context: CompilerDiagnosticContext,
    step: Mapping[object, object],
) -> tuple[Diagnostic, ...]:
    if set(step) != {_REGEX_REPLACE_FIELD}:
        return (
            _normalization_diagnostic(
                context,
                "Regex normalization steps must use only `regex_replace`.",
            ),
        )

    value = step[_REGEX_REPLACE_FIELD]
    if not isinstance(value, Mapping):
        return (
            _normalization_diagnostic(
                context,
                "`regex_replace` must be a mapping.",
            ),
        )
    if set(value) != {"pattern", "replacement"}:
        return (
            _normalization_diagnostic(
                context,
                "`regex_replace` requires only `pattern` and `replacement` fields.",
            ),
        )

    pattern = value.get("pattern")
    replacement = value.get("replacement")
    if not isinstance(pattern, str) or not isinstance(replacement, str):
        return (
            _normalization_diagnostic(
                context,
                "`regex_replace.pattern` and `regex_replace.replacement` must be strings.",
            ),
        )

    diagnostics = [_regex_diagnostic(context, pattern)]
    if _replacement_uses_backreference(replacement):
        diagnostics.append(
            context.error(
                code=INVALID_REGEX_NORMALIZATION,
                message="Regex replacement backreferences are not supported in MVP.",
                hint="Use a literal replacement string.",
            )
        )
    return tuple(diagnostic for diagnostic in diagnostics if diagnostic is not None)


def _decimal_from_number(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value) if value >= 0 else None
    if isinstance(value, float):
        if not math.isfinite(value) or value < 0:
            return None
        return Decimal(str(value))
    if isinstance(value, Decimal):
        if not value.is_finite() or value < 0:
            return None
        return value
    return None


def _literal_null_values(nulls: object) -> tuple[str, ...] | None:
    if not isinstance(nulls, Mapping):
        return None
    treat_as_null = nulls.get("treat_as_null", {})
    if not isinstance(treat_as_null, Mapping):
        return None
    values = treat_as_null.get("values", ())
    if not isinstance(values, Sequence) or isinstance(values, str):
        return None
    if not all(isinstance(value, str) for value in values):
        return None
    return tuple(values)


def _normalization_steps(normalization: object) -> tuple[_NormalizationStep, ...] | None:
    if not isinstance(normalization, Mapping):
        return None
    raw_steps = normalization.get("steps")
    if not isinstance(raw_steps, Sequence) or isinstance(raw_steps, str):
        return None

    steps: list[_NormalizationStep] = []
    for raw_step in raw_steps:
        if isinstance(raw_step, str):
            if raw_step not in _SIMPLE_NORMALIZATION_STEPS:
                return None
            steps.append(raw_step)
            continue

        if not isinstance(raw_step, Mapping):
            return None
        regex_step = _regex_replace_step(raw_step)
        if regex_step is None:
            return None
        steps.append(regex_step)

    return tuple(steps)


def _regex_replace_step(step: Mapping[object, object]) -> tuple[str, str] | None:
    if set(step) != {_REGEX_REPLACE_FIELD}:
        return None
    value = step[_REGEX_REPLACE_FIELD]
    if not isinstance(value, Mapping):
        return None
    pattern = value.get("pattern")
    replacement = value.get("replacement")
    if not isinstance(pattern, str) or not isinstance(replacement, str):
        return None
    return (pattern, replacement)


def _apply_normalization_steps(
    value: str,
    steps: Sequence[_NormalizationStep],
) -> str:
    normalized = value
    for step in steps:
        if isinstance(step, str):
            normalized = _apply_simple_normalization_step(normalized, step)
            continue

        pattern, replacement = step
        normalized = re.compile(pattern).sub(_literal_regex_replacement(replacement), normalized)
    return normalized


def _literal_regex_replacement(replacement: str) -> Callable[[re.Match[str]], str]:
    def replace(_match: re.Match[str]) -> str:
        return replacement

    return replace


def _apply_simple_normalization_step(value: str, step: str) -> str:
    if step == "trim":
        return value.strip()
    if step == "collapse_whitespace":
        return re.sub(r"\s+", " ", value)
    if step == "lower":
        return value.lower()
    if step == "upper":
        return value.upper()
    return value


def _regex_diagnostic(
    context: CompilerDiagnosticContext,
    pattern: str,
) -> Diagnostic | None:
    try:
        re.compile(pattern)
    except re.error as error:
        return context.error(
            code=INVALID_REGEX_NORMALIZATION,
            message=f"Regex pattern is invalid: {error}.",
            hint="Use the supported MVP regex subset.",
        )

    if _pattern_uses_unsupported_regex_feature(pattern):
        return context.error(
            code=INVALID_REGEX_NORMALIZATION,
            message="Regex pattern uses features outside the supported MVP regex subset.",
            hint=(
                "Avoid lookaround, backreferences, named groups, inline flags, "
                "and dialect extensions."
            ),
        )
    return None


def _pattern_uses_unsupported_regex_feature(pattern: str) -> bool:
    if any(token in pattern for token in _UNSUPPORTED_REGEX_TOKENS):
        return True
    return bool(re.search(r"\\[1-9]", pattern) or "\\g<" in pattern)


def _replacement_uses_backreference(replacement: str) -> bool:
    return bool(re.search(r"\\[1-9]", replacement) or "\\g<" in replacement)


def _sampling_diagnostic(context: CompilerDiagnosticContext, message: str) -> Diagnostic:
    return context.error(
        code=INVALID_SAMPLING,
        message=message,
        hint="Use `sampling: {default_policy: full}` or a named sampling policy.",
    )


def _null_policy_diagnostic(context: CompilerDiagnosticContext, message: str) -> Diagnostic:
    return context.error(
        code=INVALID_NULL_POLICY,
        message=message,
        hint="Use `nulls: {treat_as_null: {values: [...], regex: [...]}}`.",
    )


def _null_sentinel_diagnostic(context: CompilerDiagnosticContext, message: str) -> Diagnostic:
    return context.error(
        code=INVALID_NULL_SENTINEL,
        message=message,
        hint="Null sentinels must be explicit string values or supported regex strings.",
    )


def _normalization_diagnostic(
    context: CompilerDiagnosticContext,
    message: str,
) -> Diagnostic:
    return context.error(
        code=INVALID_NORMALIZATION,
        message=message,
        hint="Use supported normalization steps such as trim, lower, upper, or regex_replace.",
    )
