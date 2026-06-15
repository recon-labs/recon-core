"""Internal scan-budget classification for grain-key safety execution."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from recon_core.check_engine.models import CheckReason
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

SCAN_ESTIMATE_UNKNOWN: Final = "RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN"
SCAN_ESTIMATE_UNSUPPORTED: Final = "RC_RUNTIME_SCAN_ESTIMATE_UNSUPPORTED"
SCAN_BUDGET_EXCEEDED: Final = "RC_RUNTIME_SCAN_BUDGET_EXCEEDED"
UNSAFE_SCAN_PREFLIGHT: Final = "RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT"
BOUNDED_LOCAL_SCAN_REQUIRED: Final = "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"
BOUNDED_LOCAL_SCAN_ALLOWED: Final = "RC_RUNTIME_BOUNDED_LOCAL_SCAN_ALLOWED"


class ScanExecutionEnvironment(StrEnum):
    """Internal environment classes for scan-budget policy."""

    LOCAL_DEV = "local_dev"
    PRODUCTION = "production"


class ScanEstimateState(StrEnum):
    """Internal scan-estimate states used by the bounded grain-key policy."""

    PRESENT = "present"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    MALFORMED = "malformed"
    OVER_BUDGET = "over_budget"
    UNSAFE_PREFLIGHT = "unsafe_preflight"


@dataclass(frozen=True, slots=True)
class ScanBudgetContext:
    """Inputs needed to decide whether a key-safety scan may run."""

    environment: ScanExecutionEnvironment
    relation_backed: bool
    bounded: bool
    estimate_state: ScanEstimateState = ScanEstimateState.UNKNOWN


@dataclass(frozen=True, slots=True)
class ScanBudgetDecision:
    """Allow/block decision for a scan-heavy key-safety check."""

    allowed: bool
    classification: str
    message: str
    reason: CheckReason | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


def classify_scan_budget(context: ScanBudgetContext) -> ScanBudgetDecision:
    """Classify whether the bounded grain-key scan-budget policy permits execution."""
    if context.estimate_state is ScanEstimateState.UNSAFE_PREFLIGHT:
        return _blocked_decision(
            reason=CheckReason.UNSAFE_SCAN_PREFLIGHT,
            diagnostic_code=UNSAFE_SCAN_PREFLIGHT,
            message=(
                "Grain-key safety scan is not executable because scan "
                "preflight would execute or profile the query."
            ),
            hint="Use only non-executing scan estimates or explicit bounded local/dev execution.",
        )

    if context.estimate_state is ScanEstimateState.OVER_BUDGET:
        return _blocked_decision(
            reason=CheckReason.SCAN_BUDGET_EXCEEDED,
            diagnostic_code=SCAN_BUDGET_EXCEEDED,
            message="Grain-key safety scan is not executable because scan budget is exceeded.",
            hint="Reduce the scan scope or wait for later scan-budget settings support.",
        )

    if (
        context.environment is ScanExecutionEnvironment.LOCAL_DEV
        and context.relation_backed
        and context.bounded
    ):
        return ScanBudgetDecision(
            allowed=True,
            classification="bounded_local",
            message="Bounded local/dev relation-backed scan may execute.",
            diagnostics=(
                Diagnostic(
                    code=BOUNDED_LOCAL_SCAN_ALLOWED,
                    severity=DiagnosticSeverity.INFO,
                    message=(
                        "Grain-key safety scan is allowed because it is explicitly "
                        "classified as bounded local/dev relation-backed execution."
                    ),
                    resource_type="runtime_policy",
                    hint=(
                        "This classification is internal to the current grain-key "
                        "safety execution phase."
                    ),
                ),
            ),
        )

    if context.environment is ScanExecutionEnvironment.LOCAL_DEV:
        return _bounded_local_required_decision()

    if context.estimate_state is ScanEstimateState.UNKNOWN:
        return _blocked_decision(
            reason=CheckReason.SCAN_ESTIMATE_UNKNOWN,
            diagnostic_code=SCAN_ESTIMATE_UNKNOWN,
            message="Grain-key safety scan is not executable because scan estimate is unknown.",
            hint="Use explicit bounded local/dev execution or a later supported estimate policy.",
        )

    if context.estimate_state in {
        ScanEstimateState.UNAVAILABLE,
        ScanEstimateState.UNSUPPORTED,
        ScanEstimateState.MALFORMED,
    }:
        return _blocked_decision(
            reason=CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            diagnostic_code=SCAN_ESTIMATE_UNSUPPORTED,
            message=(
                "Grain-key safety scan is not executable because scan "
                "estimation is unavailable, unsupported, or malformed."
            ),
            hint="Use explicit bounded local/dev execution or a later compatible adapter policy.",
        )

    return _bounded_local_required_decision()


def _bounded_local_required_decision() -> ScanBudgetDecision:
    return _blocked_decision(
        reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
        diagnostic_code=BOUNDED_LOCAL_SCAN_REQUIRED,
        message=(
            "Grain-key safety scan is not executable because this phase allows "
            "only explicit bounded local/dev relation-backed execution."
        ),
        hint=(
            "Use a local/dev relation-backed bounded context or wait for later "
            "scan-budget settings."
        ),
    )


def _blocked_decision(
    *,
    reason: CheckReason,
    diagnostic_code: str,
    message: str,
    hint: str,
) -> ScanBudgetDecision:
    return ScanBudgetDecision(
        allowed=False,
        classification="not_executable",
        reason=reason,
        message=message,
        diagnostics=(
            Diagnostic(
                code=diagnostic_code,
                severity=DiagnosticSeverity.ERROR,
                message=message,
                hint=hint,
            ),
        ),
    )
