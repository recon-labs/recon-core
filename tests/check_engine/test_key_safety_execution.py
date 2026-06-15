import pytest

from recon_core.check_engine import CheckReason
from recon_core.check_engine.scan_budget import (
    BOUNDED_LOCAL_SCAN_REQUIRED,
    SCAN_BUDGET_EXCEEDED,
    SCAN_ESTIMATE_UNKNOWN,
    SCAN_ESTIMATE_UNSUPPORTED,
    UNSAFE_SCAN_PREFLIGHT,
    ScanBudgetContext,
    ScanEstimateState,
    ScanExecutionEnvironment,
    classify_scan_budget,
)
from recon_core.diagnostics import DiagnosticSeverity


def test_scan_budget_allows_explicit_bounded_local_relation_backed_context() -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=True,
            bounded=True,
        )
    )

    assert decision.allowed
    assert decision.reason is None
    assert decision.classification == "bounded_local"
    assert decision.message == "Bounded local/dev relation-backed scan may execute."
    assert decision.diagnostics == ()


@pytest.mark.parametrize(
    ("relation_backed", "bounded"),
    [
        (False, True),
        (True, False),
        (False, False),
    ],
)
def test_scan_budget_requires_local_relation_backed_bounded_classification(
    relation_backed: bool,
    bounded: bool,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=relation_backed,
            bounded=bounded,
        )
    )

    assert not decision.allowed
    assert decision.reason is CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED
    assert decision.classification == "not_executable"
    assert [diagnostic.code for diagnostic in decision.diagnostics] == [
        BOUNDED_LOCAL_SCAN_REQUIRED
    ]


@pytest.mark.parametrize(
    ("estimate_state", "reason", "diagnostic_code"),
    [
        (
            ScanEstimateState.PRESENT,
            CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
            BOUNDED_LOCAL_SCAN_REQUIRED,
        ),
        (
            ScanEstimateState.UNKNOWN,
            CheckReason.SCAN_ESTIMATE_UNKNOWN,
            SCAN_ESTIMATE_UNKNOWN,
        ),
        (
            ScanEstimateState.UNAVAILABLE,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.UNSUPPORTED,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.MALFORMED,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.OVER_BUDGET,
            CheckReason.SCAN_BUDGET_EXCEEDED,
            SCAN_BUDGET_EXCEEDED,
        ),
        (
            ScanEstimateState.UNSAFE_PREFLIGHT,
            CheckReason.UNSAFE_SCAN_PREFLIGHT,
            UNSAFE_SCAN_PREFLIGHT,
        ),
    ],
)
def test_scan_budget_fail_closed_paths_are_not_executable(
    estimate_state: ScanEstimateState,
    reason: CheckReason,
    diagnostic_code: str,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=estimate_state,
        )
    )

    assert not decision.allowed
    assert decision.reason is reason
    assert decision.classification == "not_executable"
    assert len(decision.diagnostics) == 1
    diagnostic = decision.diagnostics[0]
    assert diagnostic.code == diagnostic_code
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert "not executable" in diagnostic.message


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "select",
        "customer_id",
        "source_table",
        "target_table",
        "password",
    ],
)
def test_scan_budget_diagnostics_do_not_include_source_target_details(
    unsafe_text: str,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=ScanEstimateState.OVER_BUDGET,
        )
    )

    diagnostic_text = " ".join(
        part
        for diagnostic in decision.diagnostics
        for part in (diagnostic.code, diagnostic.message, diagnostic.hint or "")
    ).lower()
    assert unsafe_text not in diagnostic_text
