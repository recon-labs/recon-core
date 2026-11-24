"""Aggregate admission must fail before profile or adapter work."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from recon_core.adapters import AdapterRegistry
from recon_core.artifacts import CompiledContractLoader
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    RecordingDuckDbFactory,
    _assert_no_runtime_outputs,
    _compiled_check_payload,
    _service_result_text,
    row_count_plan,
    write_compiled_checks,
    write_compiled_contract,
    write_duckdb_row_count_run_inputs,
    write_project,
)

_PRIVATE_TOKEN = "private-synthetic-policy-value"


def _aggregate_check(*, grouped: bool = False, tolerance: object = None) -> dict[str, Any]:
    groups = ["customer_id", "month"] if grouped else []
    operation_type = "grouped_aggregate" if grouped else "aggregate"
    check_type = "grouped_aggregate_diff" if grouped else "sum_diff"
    comparison = "compare_grouped_aggregates" if grouped else "compare_aggregates"
    operations: list[dict[str, object]] = [
        {"type": operation_type, "side": side, "aggregate": "sum", "column": "revenue"}
        for side in ("source", "target")
    ]
    if grouped:
        for operation in operations:
            operation["group_by"] = list(groups)
    operations.append({"type": comparison})
    check = _compiled_check_payload(
        check_id=f"check.ecommerce_recon.customer_revenue.{check_type}",
        name=check_type,
        check_type=check_type,
        operations=operations,
        required_capabilities=[operation_type],
    )
    check["origin"] = {"kind": "metric", "name": check_type}
    check["metric"] = {"type": "sum", "column": "revenue", "group_by": groups}
    requirements = check["requirements"]
    assert isinstance(requirements, dict)
    requirements["required_columns"] = ["revenue", *groups]
    requirements["required_metrics"] = [check_type]
    check["tolerance"] = tolerance
    return check


def _run_without_profile(
    path: Path,
    check: dict[str, Any],
    *,
    policies: object = None,
    source_relation: str | None = "qa.source_customers",
    source_query: str | None = None,
) -> Any:
    # A missing profile is deliberate: blocked aggregate checks must not need one.
    write_project(path, profile="local")
    write_compiled_checks(path, checks=[check])
    write_compiled_contract(
        path,
        grain_keys=(),
        source_relation=source_relation,
        source_query=source_query,
    )
    contract_path = path / "target" / "compiled_contracts" / "customer_revenue.yml"
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if policies is not None:
        payload["policies"] = policies
    contract_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    before = contract_path.read_bytes()
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=path, adapter_registry=registry).execute()
    assert factory.adapters == []
    assert contract_path.read_bytes() == before
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    _assert_no_runtime_outputs(path)
    return result


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize(
    "tolerance",
    [
        pytest.param(-1, id="negative"),
        pytest.param(True, id="boolean"),
        pytest.param(_PRIVATE_TOKEN, id="string"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param({}, id="empty-object"),
        pytest.param({"type": "absolute"}, id="missing-value"),
        pytest.param({"type": "absolute", "value": None}, id="null-value"),
        pytest.param({"type": "absolute", "value": False}, id="boolean-value"),
        pytest.param({"type": "relative", "value": 1}, id="relative"),
        pytest.param({"type": "absolute", "value": 0, "extra": _PRIVATE_TOKEN}, id="extra"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_aggregate_tolerance_blocks_before_profile(
    tmp_path: Path, grouped: bool, tolerance: object
) -> None:
    result = _run_without_profile(tmp_path, _aggregate_check(grouped=grouped, tolerance=tolerance))
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "tolerance" in _service_result_text(result).lower()
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_unresolved_named_aggregate_policy_blocks_before_profile(
    tmp_path: Path, grouped: bool
) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(grouped=grouped),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
    )
    assert result.message == "Run completed with non-executable checks."
    assert "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize(
    "policies",
    [
        pytest.param(_PRIVATE_TOKEN, id="nonmapping"),
        pytest.param({"tolerance_policy": True}, id="boolean-reference"),
        pytest.param({"tolerance_policy": ""}, id="empty-reference"),
        pytest.param({"tolerance_policy": {"value": _PRIVATE_TOKEN}}, id="object-reference"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_named_policy_metadata_errors_before_profile(
    tmp_path: Path, policies: object
) -> None:
    result = _run_without_profile(tmp_path, _aggregate_check(), policies=policies)
    assert "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "tolerance" in _service_result_text(result).lower()
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize(
    "mutation",
    ("missing_compare", "reversed_sides", "different_column", "different_group_order", "avg"),
)
@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_aggregate_plan_rejects_unsupported_shape_before_profile(
    tmp_path: Path, mutation: str
) -> None:
    check = _aggregate_check(grouped=mutation == "different_group_order")
    operations = check["plan"]["operations"]
    if mutation == "missing_compare":
        operations.pop()
    elif mutation == "reversed_sides":
        operations[0], operations[1] = operations[1], operations[0]
    elif mutation == "different_column":
        operations[1]["column"] = _PRIVATE_TOKEN
    elif mutation == "different_group_order":
        operations[1]["group_by"] = ["month", "customer_id"]
    else:
        for operation in operations[:2]:
            operation["aggregate"] = "avg"
        check["metric"]["type"] = "avg"
    result = _run_without_profile(tmp_path, check)
    assert result.message == "Run completed with non-executable checks."
    assert "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-endpoint-precedence")
def test_aggregate_query_endpoint_is_not_executable_before_profile(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(),
        source_relation=None,
        source_query=f"select '{_PRIVATE_TOKEN}'",
    )
    assert result.message == "Run completed with non-executable checks."
    assert "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-endpoint-precedence")
def test_aggregate_invalid_relation_errors_before_profile(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path, _aggregate_check(), source_relation=f"qa..{_PRIVATE_TOKEN}"
    )
    assert "RC_ADAPTER_INVALID_RELATION" in {diagnostic.code for diagnostic in result.diagnostics}
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize("tolerance", (0, 0.1, {"type": "absolute", "value": 0.1}))
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_valid_explicit_tolerance_overrides_named_policy_without_execution(
    tmp_path: Path, grouped: bool, tolerance: object
) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(grouped=grouped, tolerance=tolerance),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
    )
    # The admission succeeds but this step does not enable aggregate execution.
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_explicit_override_does_not_fall_back_to_named_policy(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(tolerance=-1),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
    )
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_malformed_named_metadata_is_not_hidden_by_valid_override(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(tolerance=0),
        policies={"tolerance_policy": True},
    )
    assert "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_injected_public_loader_does_not_imply_verified_policy_absence(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(tmp_path, checks=[_aggregate_check(tolerance=0)])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(
        start_path=tmp_path,
        adapter_registry=registry,
        contract_loader=CompiledContractLoader(),
    ).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED"
    ]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_mixed_run_preserves_aggregate_policy_error_and_row_count(tmp_path: Path) -> None:
    write_duckdb_row_count_run_inputs(tmp_path, tmp_path / "warehouse.duckdb")
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _aggregate_check(tolerance=_PRIVATE_TOKEN),
        ],
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)
