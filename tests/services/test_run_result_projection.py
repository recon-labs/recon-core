"""Regression tests for the private allowlisted run-result projection."""

import json
from dataclasses import replace

import pytest

from recon_core.check_engine.models import (
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
    RunStatus,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services._run_lifecycle import (
    _CompiledRunPlan,
    _InvocationOutcome,
    _PlannedCheck,
    _PlannedContract,
    _RunInvocation,
)
from recon_core.services._run_result_projection import _project_run_scope
from recon_core.services.results import ExitCategory, ServiceResult

_PROJECT = "shop"
_CONTRACT = "orders"
_RUN_ID = "run-0123456789abcdef0123456789abcdef"
_TIMESTAMP = "2026-11-28T00:00:00Z"


def _planned(name: str, *, prerequisites: tuple[str, ...] = ()) -> _PlannedCheck:
    return _PlannedCheck(
        check_id=f"check.{_PROJECT}.{_CONTRACT}.{name}",
        plan_id=f"plan.{_PROJECT}.{_CONTRACT}.{name}",
        name=name,
        check_type="row_count_diff",
        prerequisites=prerequisites,
    )


def _passed(check: _PlannedCheck) -> CheckResult:
    return CheckResult(
        check_id=check.check_id,
        name="private-engine-name",
        check_type=check.check_type,
        contract_name=_CONTRACT,
        status=CheckStatus.PASS,
        executed=True,
        identity="private-key-canary",
        message="private-message-canary",
        source_value={"private-data-canary": [987654321]},
        target_value="private-target-canary",
        normalized_source_value="private-normalized-canary",
        normalized_target_value="private-normalized-target-canary",
        diff_value="private-difference-canary",
        failure_count=987654321,
        tolerance={"private-policy-canary": True},
        artifact_refs=({"path": "private-artifact-canary"},),
        sink_refs=({"path": "private-sink-canary"},),
    )


def _plan(*checks: _PlannedCheck) -> _CompiledRunPlan:
    return _CompiledRunPlan(
        project_name=_PROJECT,
        contracts=(
            _PlannedContract(
                contract_id=f"contract.{_PROJECT}.{_CONTRACT}",
                contract_name=_CONTRACT,
                project_version=None,
                checks=checks,
            ),
        ),
    )


def _result(*checks: CheckResult) -> RunResult:
    return RunResult.from_contract_results(
        run_id=_RUN_ID,
        project_name=_PROJECT,
        started_at=_TIMESTAMP,
        finished_at=_TIMESTAMP,
        contract_results=(
            ContractResult.from_check_results(contract_name=_CONTRACT, check_results=checks),
        ),
    )


def _outcome(
    plan: _CompiledRunPlan | None,
    result: RunResult | None,
    *,
    known_empty: bool = False,
) -> _InvocationOutcome:
    invocation = _RunInvocation(
        run_id=_RUN_ID,
        started_at=_TIMESTAMP,
        started_ns=100,
        project_name=_PROJECT,
        plan=plan,
        known_empty_scope=known_empty,
    )
    return invocation.finish(
        finished_at=_TIMESTAMP,
        finished_ns=200,
        run_result=result,
        service_result=ServiceResult(exit_category=ExitCategory.RUNTIME_ERROR),
    )


@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_projection_uses_plan_identity_and_structural_counts() -> None:
    first = _planned("first")
    second = _planned("second", prerequisites=(first.check_id, "private-missing-id"))
    third = _planned("third")
    blocked = CheckResult(
        check_id=second.check_id,
        name="private-engine-name",
        check_type=second.check_type,
        contract_name=_CONTRACT,
        status=CheckStatus.BLOCKED,
        reason_code=CheckReason.PREREQUISITE_MISSING,
        message="private-blocker-canary",
        blocked_by=(first.check_id, "private-missing-id", third.check_id),
        diagnostics=(
            Diagnostic(
                code="RC_TEST_PRIVATE",
                severity=DiagnosticSeverity.ERROR,
                message="private-diagnostic-canary",
            ),
        ),
    )
    outcome = _outcome(
        _plan(first, second, third), _result(_passed(first), blocked, _passed(third))
    )
    projected = _project_run_scope(outcome)

    assert projected["project_name"] == _PROJECT
    assert projected["scope"] == {
        "kind": "whole_compiled",
        "planned_contract_count": 1,
        "planned_check_count": 3,
        "finalized_check_count": 3,
        "executed_check_count": 2,
        "complete": True,
        "selection": None,
    }
    assert projected["reconciliation_status"] == "blocked"
    assert projected["summary"] == {
        "pass": 2,
        "fail": 0,
        "warn": 0,
        "error": 0,
        "skipped": 0,
        "blocked": 1,
        "not_executable": 0,
    }
    contracts = projected["contract_results"]
    assert contracts is not None
    assert contracts[0]["contract_id"] == "contract.shop.orders"
    checks = contracts[0]["check_results"]
    assert [check["check_ref"] for check in checks] == [1, 2, 3]
    assert checks[0]["check_id"] == first.check_id
    assert checks[0]["name"] == "first"
    assert checks[1]["prerequisite_refs"] == [1]
    assert checks[1]["blocked_by_refs"] == [1]
    assert checks[1]["missing_prerequisite_count"] == 1
    encoded = json.dumps(projected, allow_nan=False)
    assert "private-" not in encoded
    assert "987654321" not in encoded


@pytest.mark.regression_capture("run-loaded-compiled-scope")
@pytest.mark.parametrize("variant", ["name", "check_id", "plan_id"])
def test_projection_redacts_noncanonical_identity_without_losing_ordinal(
    variant: str,
) -> None:
    check = _planned("first")
    if variant == "name":
        check = replace(check, name="private-name-canary")
    elif variant == "check_id":
        check = replace(check, check_id="private-check-canary")
    else:
        check = replace(check, plan_id="private-plan-canary")
    projected = _project_run_scope(_outcome(_plan(check), _result(_passed(check))))

    assert projected["scope"]["complete"] is True
    contracts = projected["contract_results"]
    assert contracts is not None
    record = contracts[0]["check_results"][0]
    assert record["check_ref"] == 1
    assert record["check_id"] is None
    assert record["name"] is None
    assert record["status"] == "pass"
    assert "private-" not in json.dumps(projected, allow_nan=False)


@pytest.mark.regression_capture("run-loaded-compiled-scope")
@pytest.mark.parametrize("variant", ["foreign", "missing", "severity", "aggregate"])
def test_projection_suppresses_untrustworthy_records(variant: str) -> None:
    check = _planned("first")
    result = _result(_passed(check))
    if variant == "foreign":
        result = replace(result, run_id="private-foreign-id")
    elif variant == "missing":
        result = _result()
    elif variant == "severity":
        result = _result(replace(_passed(check), severity="private-severity"))
    else:
        result = replace(result, status=RunStatus.FAIL)
    projected = _project_run_scope(_outcome(_plan(check), result))

    assert projected["scope"]["planned_check_count"] == 1
    assert projected["scope"]["complete"] is False
    assert projected["scope"]["finalized_check_count"] is None
    assert projected["scope"]["executed_check_count"] is None
    assert projected["reconciliation_status"] is None
    assert projected["summary"] is None
    assert projected["contract_results"] is None
    assert "private-" not in json.dumps(projected, allow_nan=False)


@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_projection_distinguishes_known_empty_from_unavailable_scope() -> None:
    empty = _project_run_scope(_outcome(None, None, known_empty=True))
    unknown = _project_run_scope(_outcome(None, None))

    assert empty["scope"]["planned_contract_count"] is None
    assert empty["scope"]["planned_check_count"] == 0
    assert empty["scope"]["finalized_check_count"] == 0
    assert empty["scope"]["executed_check_count"] == 0
    assert empty["scope"]["complete"] is None
    assert empty["reconciliation_status"] == "no_checks"
    assert empty["contract_results"] is None
    assert empty["summary"] == dict.fromkeys((status.value for status in CheckStatus), 0)
    assert unknown["scope"]["planned_check_count"] is None
    assert unknown["scope"]["finalized_check_count"] is None
    assert unknown["scope"]["executed_check_count"] is None
    assert unknown["reconciliation_status"] is None
    assert unknown["summary"] is None
    assert unknown["contract_results"] is None

    # A returned record without a validated plan is inconsistent, not merely unknown.
    unplanned = _project_run_scope(_outcome(None, _result(_passed(_planned("first")))))
    assert unplanned["scope"]["complete"] is False
    assert unplanned["scope"]["finalized_check_count"] is None
    assert unplanned["scope"]["executed_check_count"] is None
    assert unplanned["reconciliation_status"] is None
    assert unplanned["summary"] is None
    assert unplanned["contract_results"] is None
