from recon_core.compiler import (
    COMPILED_ARTIFACT_FILENAME_COLLISION,
    INVALID_STABLE_ID_PART,
    compile_project,
)
from recon_core.compiler.check_packs import VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
from recon_core.compiler.models import CompiledArtifactType
from recon_core.parser import DUPLICATE_CONTRACT, AuthoredContract, AuthoredEndpoint
from recon_core.parser.models import SourceLocation


def test_compile_project_builds_contract_and_checks_artifacts() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(_contract(),),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert result.succeeded
    assert result.diagnostics == ()
    assert len(result.contracts) == 1

    compiled = result.contracts[0]
    contract_artifact = compiled.contract_artifact.to_dict()
    checks_artifact = compiled.checks_artifact.to_dict()

    assert contract_artifact["artifact_type"] == CompiledArtifactType.COMPILED_CONTRACT.value
    assert contract_artifact["artifact_version"] == 1
    assert contract_artifact["recon_version"] == "0.0.test"
    assert contract_artifact["generated_at"] == "2026-05-23T12:00:00Z"
    assert contract_artifact["invocation_id"] == "01JTESTINVOCATION0000000000"
    assert contract_artifact["contract"]["id"] == "contract.ecommerce_recon.customer_revenue"
    assert contract_artifact["identity"]["grain"]["keys"] == ["customer_id", "month"]
    assert contract_artifact["source"] == {
        "connection": "legacy",
        "relation": "qa.customer_source",
        "query": None,
    }

    assert checks_artifact["artifact_type"] == CompiledArtifactType.COMPILED_CHECKS.value
    assert [check["name"] for check in checks_artifact["checks"]] == [
        "row_count_diff",
        "missing_keys",
        "extra_keys",
        "null_source_keys",
        "null_target_keys",
        "duplicate_source_keys",
        "duplicate_target_keys",
        "total_revenue",
        "revenue_by_month",
    ]


def test_compile_project_check_artifact_contains_expanded_plans_and_metric_checks() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(_contract(),),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    checks = {
        check["name"]: check for check in result.contracts[0].checks_artifact.to_dict()["checks"]
    }

    assert checks["null_source_keys"]["plan"]["operations"][0] == {
        "type": "null_key",
        "side": "source",
        "identity": {
            "kind": "grain",
            "keys": ["customer_id", "month"],
        },
    }
    assert checks["total_revenue"]["type"] == "sum_diff"
    assert checks["total_revenue"]["plan"]["operations"][-1] == {"type": "compare_aggregates"}
    assert checks["revenue_by_month"]["type"] == "grouped_aggregate_diff"
    assert checks["revenue_by_month"]["plan"]["operations"][-1] == {
        "type": "compare_grouped_aggregates"
    }
    assert checks["revenue_by_month"]["tolerance"] == 0.01
    assert checks["row_count_diff"]["sampling"] == {"mode": "full"}


def test_compile_project_validation_errors_are_embedded_without_success() -> None:
    contract = _contract(include_grain=False)

    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(contract,),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
    ]
    assert result.contracts[0].checks_artifact.checks == ()
    assert result.contracts[0].checks_artifact.diagnostics == result.diagnostics


def test_compile_project_returns_diagnostic_for_invalid_project_stable_id_part() -> None:
    result = compile_project(
        project_name="ecommerce-recon",
        project_version="0.1.0",
        contracts=(_contract(),),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_STABLE_ID_PART]
    assert result.diagnostics[0].resource_type == "project"
    assert "ecommerce-recon" in result.diagnostics[0].message


def test_compile_project_returns_diagnostic_for_invalid_contract_stable_id_part() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(_contract(name="customer-revenue"),),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_STABLE_ID_PART]
    assert result.diagnostics[0].resource_type == "contract"
    assert result.diagnostics[0].path == "contracts/customer-revenue.yml"


def test_compile_project_returns_diagnostic_for_duplicate_contract_names() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(_contract(), _contract(source_path="contracts/duplicate.yml")),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [DUPLICATE_CONTRACT]
    assert result.diagnostics[0].resource_type == "contract"
    assert result.diagnostics[0].resource_name == "customer_revenue"
    assert result.diagnostics[0].path == "contracts/duplicate.yml"


def test_compile_project_returns_diagnostic_for_case_colliding_artifact_names() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(
            _contract(name="Sales", source_path="contracts/sales_upper.yml"),
            _contract(name="sales", source_path="contracts/sales_lower.yml"),
        ),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        COMPILED_ARTIFACT_FILENAME_COLLISION
    ]
    assert result.diagnostics[0].resource_type == "contract"
    assert result.diagnostics[0].resource_name == "sales"
    assert result.diagnostics[0].path == "contracts/sales_lower.yml"
    assert "Sales.yml" in result.diagnostics[0].message
    assert "sales.yml" in result.diagnostics[0].message


def test_compile_project_returns_diagnostic_for_invalid_metric_stable_id_part() -> None:
    result = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(_contract(metric_name="total-revenue"),),
        invocation_id="01JTESTINVOCATION0000000000",
        generated_at="2026-05-23T12:00:00Z",
        recon_version="0.0.test",
    )

    assert not result.succeeded
    assert len(result.contracts) == 1
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_STABLE_ID_PART]
    assert result.diagnostics[0].resource_type == "metric"
    assert result.diagnostics[0].resource_name == "total-revenue"
    assert result.contracts[0].checks_artifact.checks == ()


def _contract(
    *,
    name: str = "customer_revenue",
    include_grain: bool = True,
    metric_name: str = "total_revenue",
    source_path: str | None = None,
) -> AuthoredContract:
    grain: dict[str, object] | None = None
    if include_grain:
        grain = {"keys": ["customer_id", "month"]}

    return AuthoredContract(
        name=name,
        version=1,
        source=AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
        target=AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
        checks={"use": ["recon_core.basic_equivalence"]},
        source_location=SourceLocation(path=source_path or f"contracts/{name}.yml"),
        grain=grain,
        metrics=(
            {"name": metric_name, "type": "sum", "column": "revenue"},
            {
                "name": "revenue_by_month",
                "type": "sum",
                "column": "revenue",
                "group_by": ["month"],
                "tolerance": 0.01,
            },
        ),
        sampling={"default_policy": "full"},
    )
