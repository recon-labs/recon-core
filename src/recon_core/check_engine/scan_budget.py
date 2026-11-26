"""Internal scan-budget classification for grain-key safety execution."""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import ceil
from typing import Final

from recon_core.check_engine.models import CheckReason
from recon_core.config._local_resource_policy import _LocalResourcePolicy
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
    return _classify_scan_budget(context, label="Grain-key safety")


def _classify_scan_budget(context: ScanBudgetContext, *, label: str) -> ScanBudgetDecision:
    if context.estimate_state is ScanEstimateState.UNSAFE_PREFLIGHT:
        return _blocked_decision(
            reason=CheckReason.UNSAFE_SCAN_PREFLIGHT,
            diagnostic_code=UNSAFE_SCAN_PREFLIGHT,
            message=(
                f"{label} scan is not executable because scan "
                "preflight would execute or profile the query."
            ),
            hint=("Use only non-executing scan estimates or the internal local/dev scan guard."),
        )

    if context.estimate_state is ScanEstimateState.OVER_BUDGET:
        return _blocked_decision(
            reason=CheckReason.SCAN_BUDGET_EXCEEDED,
            diagnostic_code=SCAN_BUDGET_EXCEEDED,
            message=f"{label} scan is not executable because scan budget is exceeded.",
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
                        f"{label} scan is allowed because the internal "
                        "bounded local/dev relation-backed scan guard passed."
                    ),
                    resource_type="runtime_policy",
                    hint=(
                        f"This classification is internal to the current {label.lower()} "
                        "execution phase."
                    ),
                ),
            ),
        )

    if context.environment is ScanExecutionEnvironment.LOCAL_DEV:
        return _bounded_local_required_decision(label=label)

    if context.estimate_state is ScanEstimateState.UNKNOWN:
        return _blocked_decision(
            reason=CheckReason.SCAN_ESTIMATE_UNKNOWN,
            diagnostic_code=SCAN_ESTIMATE_UNKNOWN,
            message=f"{label} scan is not executable because scan estimate is unknown.",
            hint=("Use the internal local/dev scan guard or a later supported estimate policy."),
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
                f"{label} scan is not executable because scan "
                "estimation is unavailable, unsupported, or malformed."
            ),
            hint=("Use the internal local/dev scan guard or a later compatible adapter policy."),
        )

    return _bounded_local_required_decision(label=label)


def missing_scan_budget_decision() -> ScanBudgetDecision:
    """Return the fail-closed decision used when no key-safety scan decision exists."""
    return classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=ScanEstimateState.UNKNOWN,
        )
    )


def _bounded_local_required_decision(*, label: str) -> ScanBudgetDecision:
    return _blocked_decision(
        reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
        diagnostic_code=BOUNDED_LOCAL_SCAN_REQUIRED,
        message=(
            f"{label} scan is not executable because this phase allows "
            "only internal bounded local/dev relation-backed execution."
        ),
        hint=(
            "Use a context that passes the internal local/dev scan guard or wait "
            "for later scan-budget settings."
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


def _aggregate_scan_budget_decision(decision: ScanBudgetDecision) -> ScanBudgetDecision:
    """Reconstruct safe aggregate wording using the shared classification policy."""
    bounded_context = ScanBudgetContext(
        environment=ScanExecutionEnvironment.LOCAL_DEV,
        relation_backed=True,
        bounded=True,
    )
    if (
        type(decision) is ScanBudgetDecision
        and decision.allowed is True
        and decision == classify_scan_budget(bounded_context)
    ):
        return _classify_scan_budget(bounded_context, label="Aggregate")
    states: dict[CheckReason | None, ScanEstimateState] = {
        CheckReason.SCAN_ESTIMATE_UNKNOWN: ScanEstimateState.UNKNOWN,
        CheckReason.SCAN_ESTIMATE_UNSUPPORTED: ScanEstimateState.UNSUPPORTED,
        CheckReason.SCAN_BUDGET_EXCEEDED: ScanEstimateState.OVER_BUDGET,
        CheckReason.UNSAFE_SCAN_PREFLIGHT: ScanEstimateState.UNSAFE_PREFLIGHT,
        CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED: ScanEstimateState.PRESENT,
    }
    return _classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=states.get(
                (
                    decision.reason
                    if type(decision) is ScanBudgetDecision and type(decision.reason) is CheckReason
                    else None
                ),
                ScanEstimateState.UNKNOWN,
            ),
        ),
        label="Aggregate",
    )


@dataclass(frozen=True, slots=True)
class _LocalResourceInputs:
    """Independently established effective observations, not admission proof.

    None means unavailable; a measured zero remains zero. Native automatic
    memory and thread settings are recommendations, not hardware ceilings.
    """

    memory_headroom_bytes: int | None = None
    cpu_capacity: Fraction | None = None
    scratch_free_bytes: int | None = None
    scratch_memory_backed: bool | None = None
    native_memory_bytes: int | None = None
    native_threads: int | None = None
    native_spill_ceiling_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class _LocalResourceTuning:
    """Adapter-supplied candidate reserve ratios, not universal defaults."""

    memory_reserve_divisor: int
    disk_reserve_divisor: int

    def __post_init__(self) -> None:
        for divisor in (self.memory_reserve_divisor, self.disk_reserve_divisor):
            if type(divisor) is not int or divisor < 2:
                raise ValueError("Invalid resource reserve tuning.")


@dataclass(frozen=True, slots=True)
class _LocalResourceTargets:
    """Calculated managed targets, never a guarantee of actual enforcement."""

    managed_memory_bytes: int | None
    threads: int | None
    spill_bytes: int | None
    memory_reserve_bytes: int | None
    disk_reserve_bytes: int | None
    reduced_authored_targets: tuple[str, ...]


def _remaining_after_reserve(
    available: int | None, authored_reserve: int | None, divisor: int
) -> tuple[int | None, int | None]:
    if available is None:
        return None, None
    reserve = (
        authored_reserve if authored_reserve is not None else (available + divisor - 1) // divisor
    )
    return max(0, available - reserve), reserve


def _bounded_target(available: int | None, *ceilings: int | None) -> int | None:
    if available is None:
        return None
    return min((available, *(value for value in ceilings if value is not None)))


def _preferred_target(authored: int | None, native: int | None) -> int | None:
    return authored if authored is not None else native


def _calculate_local_resource_targets(
    policy: _LocalResourcePolicy,
    inputs: _LocalResourceInputs,
    tuning: _LocalResourceTuning,
) -> _LocalResourceTargets:
    """Calculate candidate settings without admitting, probing or executing a check."""

    for value in (
        inputs.memory_headroom_bytes,
        inputs.scratch_free_bytes,
        inputs.native_memory_bytes,
        inputs.native_threads,
        inputs.native_spill_ceiling_bytes,
    ):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid resource observation.")
    if inputs.cpu_capacity is not None and (
        type(inputs.cpu_capacity) is not Fraction or inputs.cpu_capacity < 0
    ):
        raise ValueError("Invalid resource observation.")
    if inputs.scratch_memory_backed is not None and type(inputs.scratch_memory_backed) is not bool:
        raise ValueError("Invalid resource observation.")

    memory_available, memory_reserve = _remaining_after_reserve(
        inputs.memory_headroom_bytes, policy.memory_reserve_bytes, tuning.memory_reserve_divisor
    )
    memory = _bounded_target(
        memory_available, _preferred_target(policy.managed_memory_bytes, inputs.native_memory_bytes)
    )
    cpu = ceil(inputs.cpu_capacity) if inputs.cpu_capacity is not None else None
    threads = _bounded_target(cpu, _preferred_target(policy.threads, inputs.native_threads))
    disk_available, disk_reserve = _remaining_after_reserve(
        inputs.scratch_free_bytes, policy.disk_reserve_bytes, tuning.disk_reserve_divisor
    )
    if inputs.scratch_memory_backed is None:
        disk_available = None
    elif inputs.scratch_memory_backed:
        if memory_available is None or memory is None:
            disk_available = None
        else:
            disk_available = _bounded_target(disk_available, memory_available - memory)
    spill = _bounded_target(disk_available, policy.spill_bytes, inputs.native_spill_ceiling_bytes)

    reduced = tuple(
        name
        for name, authored, effective in (
            ("managed-memory-mib", policy.managed_memory_bytes, memory),
            ("threads", policy.threads, threads),
            ("spill-mib", policy.spill_bytes, spill),
        )
        if authored is not None and effective is not None and effective < authored
    )
    return _LocalResourceTargets(
        managed_memory_bytes=memory,
        threads=threads,
        spill_bytes=spill,
        memory_reserve_bytes=memory_reserve,
        disk_reserve_bytes=disk_reserve,
        reduced_authored_targets=reduced,
    )
