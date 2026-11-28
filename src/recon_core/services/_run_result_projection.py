"""Private allowlisted run-result projection; never serialize execution models."""

from collections import Counter
from typing import Literal, TypedDict

from recon_core.check_engine.models import CheckResult, CheckStatus, RunResult, RunStatus
from recon_core.compiler.ids import (
    build_check_id,
    build_contract_id,
    build_plan_id,
    is_valid_stable_id_part,
)
from recon_core.compiler.models import CompiledCheckType
from recon_core.services._run_lifecycle import (
    _CompiledRunPlan,
    _InvocationOutcome,
    _PlannedCheck,
    _PlannedContract,
)


_KNOWN_CHECK_TYPES = frozenset(kind.value for kind in CompiledCheckType)


class _PublicScope(TypedDict):
    kind: Literal["whole_compiled", "unknown"]
    planned_contract_count: int | None
    planned_check_count: int | None
    finalized_check_count: int | None
    executed_check_count: int | None
    complete: bool | None
    selection: None


class _ProjectedCheck(TypedDict):
    check_ref: int
    check_id: str | None
    name: str | None
    check_type: str | None
    status: str
    severity: str
    executed: bool
    reason_code: str | None
    prerequisite_refs: list[int]
    blocked_by_refs: list[int]
    missing_prerequisite_count: int


class _ProjectedContract(TypedDict):
    contract_ref: int
    contract_id: str | None
    contract_name: str | None
    status: str
    check_results: list[_ProjectedCheck]


class _ScopeProjection(TypedDict):
    project_name: str | None
    scope: _PublicScope
    reconciliation_status: str | None
    summary: dict[str, int] | None
    contract_results: list[_ProjectedContract] | None


def _project_run_scope(outcome: _InvocationOutcome) -> _ScopeProjection:
    """Project verified record scope, never private retained or foreign records."""
    facts = outcome.scope_facts
    plan = outcome.plan
    result = outcome.run_result
    project_name = _canonical_name(outcome.project_name)
    scope: _PublicScope = {
        "kind": "whole_compiled" if plan is not None else "unknown",
        "planned_contract_count": facts.planned_contract_count,
        "planned_check_count": facts.planned_check_count,
        "finalized_check_count": None,
        "executed_check_count": None,
        "complete": facts.complete,
        "selection": None,
    }
    projection: _ScopeProjection = {
        "project_name": project_name,
        "scope": scope,
        "reconciliation_status": None,
        "summary": None,
        "contract_results": None,
    }
    if facts.complete is True and plan is not None and result is not None:
        records = _project_contracts(plan, result, project_name)
        counts = Counter(
            check["status"] for contract in records for check in contract["check_results"]
        )
        scope["finalized_check_count"] = facts.finalized_check_count
        scope["executed_check_count"] = facts.executed_check_count
        projection["reconciliation_status"] = result.status.value
        projection["summary"] = {status.value: counts[status.value] for status in CheckStatus}
        projection["contract_results"] = records
    elif plan is None and result is None and facts.planned_check_count == 0:
        # Only the authoritative empty-loader path supplies a zero without a plan.
        scope["finalized_check_count"] = 0
        scope["executed_check_count"] = 0
        projection["reconciliation_status"] = RunStatus.NO_CHECKS.value
        projection["summary"] = {status.value: 0 for status in CheckStatus}
    return projection


def _canonical_name(value: str | None) -> str | None:
    if isinstance(value, str) and is_valid_stable_id_part(value):
        return value
    return None


def _canonical_contract_id(project_name: str | None, contract: _PlannedContract) -> str | None:
    if (
        project_name is not None
        and _canonical_name(contract.contract_name) is not None
        and contract.contract_id == build_contract_id(project_name, contract.contract_name)
    ):
        return contract.contract_id
    return None


def _canonical_check_id(
    project_name: str | None, contract_name: str | None, check: _PlannedCheck
) -> str | None:
    if (
        project_name is not None
        and contract_name is not None
        and _canonical_name(check.name) is not None
        and check.check_id == build_check_id(project_name, contract_name, check.name)
        and check.plan_id == build_plan_id(project_name, contract_name, check.name)
    ):
        return check.check_id
    return None


def _project_contracts(
    plan: _CompiledRunPlan, result: RunResult, project_name: str | None
) -> list[_ProjectedContract]:
    check_refs = {
        check.check_id: index
        for index, check in enumerate(
            (check for contract in plan.contracts for check in contract.checks), start=1
        )
    }
    records: list[_ProjectedContract] = []
    for contract_ref, (planned, actual) in enumerate(
        zip(plan.contracts, result.contract_results, strict=True), start=1
    ):
        contract_id = _canonical_contract_id(project_name, planned)
        contract_name = planned.contract_name if contract_id is not None else None
        records.append(
            {
                "contract_ref": contract_ref,
                "contract_id": contract_id,
                "contract_name": contract_name,
                "status": actual.status.value,
                "check_results": [
                    _project_check(project_name, contract_name, check, check_result, check_refs)
                    for check, check_result in zip(
                        planned.checks, actual.check_results, strict=True
                    )
                ],
            }
        )
    return records


def _project_check(
    project_name: str | None,
    contract_name: str | None,
    check: _PlannedCheck,
    result: CheckResult,
    check_refs: dict[str, int],
) -> _ProjectedCheck:
    check_id = _canonical_check_id(project_name, contract_name, check)
    prerequisite_refs = [
        check_refs[prerequisite]
        for prerequisite in check.prerequisites
        if prerequisite in check_refs
    ]
    # A result cannot introduce new prerequisite edges. Use only observed blockers
    # that refer to an existing prerequisite in the validated invocation plan.
    prerequisite_ids = set(check.prerequisites)
    blocked_by_refs = [
        check_refs[blocker]
        for blocker in result.blocked_by
        if blocker in prerequisite_ids and blocker in check_refs
    ]
    return {
        "check_ref": check_refs[check.check_id],
        "check_id": check_id,
        "name": check.name if check_id is not None else None,
        "check_type": check.check_type if check.check_type in _KNOWN_CHECK_TYPES else None,
        "status": result.status.value,
        "severity": result.severity,
        "executed": result.executed,
        "reason_code": result.reason_code.value if result.reason_code is not None else None,
        "prerequisite_refs": prerequisite_refs,
        "blocked_by_refs": blocked_by_refs,
        "missing_prerequisite_count": len(check.prerequisites) - len(prerequisite_refs),
    }
