import json

import pytest

from recon_core.check_engine import (
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
    RunStatus,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def _diagnostic(message: str) -> Diagnostic:
    return Diagnostic(
        code="RC_RUNTIME_CHECK_NOT_EXECUTABLE",
        severity=DiagnosticSeverity.ERROR,
        message=message,
    )


def test_status_and_reason_values_match_locked_taxonomy() -> None:
    assert [status.value for status in CheckStatus] == [
        "pass",
        "fail",
        "warn",
        "error",
        "skipped",
        "blocked",
        "not_executable",
    ]
    assert [status.value for status in RunStatus] == [
        "pass",
        "fail",
        "warn",
        "error",
        "skipped",
        "blocked",
        "not_executable",
        "no_checks",
    ]
    assert [reason.value for reason in CheckReason] == [
        "prerequisite_failed",
        "prerequisite_error",
        "prerequisite_missing",
        "prerequisite_not_executable",
        "unsupported_check_type",
        "unsupported_typed_operation",
        "missing_engine_capability",
        "unsupported_execution_placement",
        "unsupported_materialization_policy",
        "scan_estimate_unknown",
        "scan_estimate_unsupported",
        "scan_budget_exceeded",
        "unsafe_scan_preflight",
        "bounded_local_scan_required",
        "not_implemented_in_current_phase",
        "skipped_by_policy",
        "selected_out",
    ]


def test_check_result_serializes_non_executable_result_deterministically() -> None:
    diagnostic = Diagnostic(
        code="RC_RUNTIME_CHECK_NOT_EXECUTABLE",
        severity=DiagnosticSeverity.ERROR,
        message="Check belongs to a later execution phase.",
        resource_type="compiled_check",
        resource_name="customer_revenue.row_count_diff",
        path="target/compiled_checks/customer_revenue.yml",
        hint="Run this again after the assigned execution phase is implemented.",
    )
    result = CheckResult(
        check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
        name="row_count_diff",
        check_type="row_count_diff",
        contract_name="customer_revenue",
        status=CheckStatus.NOT_EXECUTABLE,
        severity="error",
        executed=False,
        reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
        identity="none",
        message="Check belongs to a later execution phase.",
        diagnostics=(diagnostic,),
    )

    assert result.to_dict() == {
        "check_id": "check.ecommerce_recon.customer_revenue.row_count_diff",
        "name": "row_count_diff",
        "check_type": "row_count_diff",
        "contract_name": "customer_revenue",
        "status": "not_executable",
        "severity": "error",
        "executed": False,
        "reason_code": "not_implemented_in_current_phase",
        "identity": "none",
        "message": "Check belongs to a later execution phase.",
        "source_value": None,
        "target_value": None,
        "normalized_source_value": None,
        "normalized_target_value": None,
        "diff_value": None,
        "tolerance": None,
        "nulls": None,
        "normalization": None,
        "failure_count": None,
        "blocked_by": [],
        "artifact_refs": [],
        "sink_refs": [],
        "diagnostics": [diagnostic.to_dict()],
    }
    assert json.loads(json.dumps(result.to_dict()))["status"] == "not_executable"


def test_blocked_result_serializes_blockers_and_matching_reason() -> None:
    diagnostic = _diagnostic("Check did not run because a prerequisite failed.")
    result = CheckResult(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        contract_name="customer_revenue",
        status=CheckStatus.BLOCKED,
        executed=False,
        reason_code=CheckReason.PREREQUISITE_FAILED,
        message="Check did not run because a prerequisite failed.",
        blocked_by=("check.ecommerce_recon.customer_revenue.duplicate_source_keys",),
        diagnostics=(diagnostic,),
    )

    assert result.to_dict()["blocked_by"] == [
        "check.ecommerce_recon.customer_revenue.duplicate_source_keys"
    ]
    assert result.to_dict()["reason_code"] == "prerequisite_failed"


@pytest.mark.parametrize(
    ("status", "executed", "reason_code", "blocked_by", "message"),
    [
        (
            CheckStatus.PASS,
            False,
            None,
            (),
            "pass result requires executed=True",
        ),
        (
            CheckStatus.NOT_EXECUTABLE,
            False,
            None,
            (),
            "not_executable result requires a reason_code",
        ),
        (
            CheckStatus.BLOCKED,
            False,
            CheckReason.PREREQUISITE_FAILED,
            (),
            "blocked result requires blocked_by",
        ),
        (
            CheckStatus.NOT_EXECUTABLE,
            False,
            CheckReason.PREREQUISITE_FAILED,
            (),
            "requires status blocked",
        ),
        (
            CheckStatus.SKIPPED,
            True,
            CheckReason.SKIPPED_BY_POLICY,
            (),
            "skipped result requires executed=False",
        ),
    ],
)
def test_check_result_rejects_invalid_status_reason_combinations(
    status: CheckStatus,
    executed: bool,
    reason_code: CheckReason | None,
    blocked_by: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=status,
            executed=executed,
            reason_code=reason_code,
            blocked_by=blocked_by,
        )


@pytest.mark.parametrize(
    ("status", "reason_code", "blocked_by", "message", "diagnostics", "expected_error"),
    [
        (
            CheckStatus.BLOCKED,
            CheckReason.PREREQUISITE_FAILED,
            ("check.ecommerce_recon.customer_revenue.duplicate_source_keys",),
            None,
            (_diagnostic("Check did not run."),),
            "blocked result requires a message",
        ),
        (
            CheckStatus.NOT_EXECUTABLE,
            CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
            (),
            "",
            (_diagnostic("Check did not run."),),
            "not_executable result requires a message",
        ),
        (
            CheckStatus.SKIPPED,
            CheckReason.SKIPPED_BY_POLICY,
            (),
            "Check was skipped by policy.",
            (),
            "skipped result requires diagnostics",
        ),
    ],
)
def test_non_executed_result_requires_message_and_diagnostics(
    status: CheckStatus,
    reason_code: CheckReason,
    blocked_by: tuple[str, ...],
    message: str | None,
    diagnostics: tuple[Diagnostic, ...],
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=status,
            executed=False,
            reason_code=reason_code,
            blocked_by=blocked_by,
            message=message,
            diagnostics=diagnostics,
        )


@pytest.mark.parametrize(
    "reason_code",
    [
        CheckReason.SCAN_ESTIMATE_UNKNOWN,
        CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
        CheckReason.SCAN_BUDGET_EXCEEDED,
        CheckReason.UNSAFE_SCAN_PREFLIGHT,
        CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
    ],
)
def test_scan_budget_reasons_are_not_executable_reasons(
    reason_code: CheckReason,
) -> None:
    result = CheckResult(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        contract_name="customer_revenue",
        status=CheckStatus.NOT_EXECUTABLE,
        executed=False,
        reason_code=reason_code,
        message="Check did not run because scan-budget policy blocked execution.",
        diagnostics=(_diagnostic("Check did not run."),),
    )

    assert result.reason_code is reason_code


def test_non_executed_result_rejects_value_and_output_refs() -> None:
    with pytest.raises(ValueError, match="non-executed result cannot include value fields"):
        CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.NOT_EXECUTABLE,
            executed=False,
            reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
            message="Check belongs to a later execution phase.",
            diagnostics=(_diagnostic("Check belongs to a later execution phase."),),
            source_value=12,
        )

    with pytest.raises(ValueError, match="non-executed result cannot include output refs"):
        CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.NOT_EXECUTABLE,
            executed=False,
            reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
            message="Check belongs to a later execution phase.",
            diagnostics=(_diagnostic("Check belongs to a later execution phase."),),
            artifact_refs=("target/run_results.json",),
        )


def test_contract_and_run_results_serialize_without_command_result_fields() -> None:
    check = CheckResult(
        check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
        name="row_count_diff",
        check_type="row_count_diff",
        contract_name="customer_revenue",
        status=CheckStatus.NOT_EXECUTABLE,
        executed=False,
        reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
        message="Check belongs to a later execution phase.",
        diagnostics=(_diagnostic("Check belongs to a later execution phase."),),
    )
    contract = ContractResult.from_check_results(
        contract_name="customer_revenue",
        check_results=(check,),
    )
    run = RunResult.from_contract_results(
        run_id="run-001",
        project_name="ecommerce_recon",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        contract_results=(contract,),
    )

    payload = run.to_dict()

    assert payload["status"] == "not_executable"
    assert payload["contract_results"][0]["status"] == "not_executable"
    assert payload["artifact_refs"] == []
    assert payload["sink_refs"] == []
    assert "exit_category" not in payload
    assert "exit_code" not in payload
