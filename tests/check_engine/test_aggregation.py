import pytest

from recon_core.check_engine import (
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
    RunStatus,
    aggregate_check_status,
    aggregate_contract_status,
)


def _result(status: CheckStatus, name: str) -> CheckResult:
    if status in {CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.WARN}:
        return CheckResult(
            check_id=f"check.ecommerce_recon.customer_revenue.{name}",
            name=name,
            check_type=name,
            contract_name="customer_revenue",
            status=status,
            executed=True,
        )
    if status is CheckStatus.BLOCKED:
        return CheckResult(
            check_id=f"check.ecommerce_recon.customer_revenue.{name}",
            name=name,
            check_type=name,
            contract_name="customer_revenue",
            status=status,
            executed=False,
            reason_code=CheckReason.PREREQUISITE_FAILED,
            blocked_by=("check.ecommerce_recon.customer_revenue.duplicate_source_keys",),
        )
    if status is CheckStatus.NOT_EXECUTABLE:
        return CheckResult(
            check_id=f"check.ecommerce_recon.customer_revenue.{name}",
            name=name,
            check_type=name,
            contract_name="customer_revenue",
            status=status,
            executed=False,
            reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
        )
    if status is CheckStatus.SKIPPED:
        return CheckResult(
            check_id=f"check.ecommerce_recon.customer_revenue.{name}",
            name=name,
            check_type=name,
            contract_name="customer_revenue",
            status=status,
            executed=False,
            reason_code=CheckReason.SKIPPED_BY_POLICY,
        )
    return CheckResult(
        check_id=f"check.ecommerce_recon.customer_revenue.{name}",
        name=name,
        check_type=name,
        contract_name="customer_revenue",
        status=status,
        executed=False,
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((), RunStatus.NO_CHECKS),
        ((CheckStatus.ERROR, CheckStatus.FAIL), RunStatus.ERROR),
        ((CheckStatus.FAIL, CheckStatus.BLOCKED), RunStatus.FAIL),
        ((CheckStatus.BLOCKED, CheckStatus.NOT_EXECUTABLE), RunStatus.BLOCKED),
        ((CheckStatus.NOT_EXECUTABLE, CheckStatus.WARN), RunStatus.NOT_EXECUTABLE),
        ((CheckStatus.WARN, CheckStatus.PASS), RunStatus.WARN),
        ((CheckStatus.PASS, CheckStatus.SKIPPED), RunStatus.PASS),
        ((CheckStatus.SKIPPED, CheckStatus.SKIPPED), RunStatus.SKIPPED),
        ((CheckStatus.PASS, CheckStatus.PASS), RunStatus.PASS),
    ],
)
def test_check_status_aggregation_uses_locked_precedence(
    statuses: tuple[CheckStatus, ...],
    expected: RunStatus,
) -> None:
    results = tuple(_result(status, f"check_{index}") for index, status in enumerate(statuses))

    assert aggregate_check_status(results) is expected


def test_contract_result_from_empty_checks_is_no_checks() -> None:
    result = ContractResult.from_check_results(
        contract_name="customer_revenue",
        check_results=(),
    )

    assert result.status is RunStatus.NO_CHECKS
    assert result.to_dict()["status"] == "no_checks"
    assert result.to_dict()["check_results"] == []


def test_run_status_aggregation_uses_contract_result_precedence() -> None:
    error_contract = ContractResult.from_check_results(
        contract_name="customer_revenue",
        check_results=(_result(CheckStatus.ERROR, "engine_error"),),
    )
    failed_contract = ContractResult.from_check_results(
        contract_name="order_revenue",
        check_results=(_result(CheckStatus.FAIL, "row_count_diff"),),
    )

    assert aggregate_contract_status((failed_contract, error_contract)) is RunStatus.ERROR

    run = RunResult.from_contract_results(
        run_id="run-001",
        project_name="ecommerce_recon",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        contract_results=(failed_contract, error_contract),
    )

    assert run.status is RunStatus.ERROR
    assert run.to_dict()["status"] == "error"


def test_run_result_from_empty_contracts_is_no_checks() -> None:
    run = RunResult.from_contract_results(
        run_id="run-001",
        project_name="ecommerce_recon",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        contract_results=(),
    )

    assert run.status is RunStatus.NO_CHECKS
    assert run.to_dict()["contract_results"] == []
