from recon_core.compiler import compile_project
from recon_core.compiler.check_packs import VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
from recon_core.compiler.models import CompiledArtifactType
from recon_core.parser import AuthoredContract, AuthoredEndpoint
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


def _contract(
    *,
    include_grain: bool = True,
) -> AuthoredContract:
    grain: dict[str, object] | None = None
    if include_grain:
        grain = {"keys": ["customer_id", "month"]}

    return AuthoredContract(
        name="customer_revenue",
        version=1,
        source=AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
        target=AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
        checks={"use": ["recon_core.basic_equivalence"]},
        source_location=SourceLocation(path="contracts/customer_revenue.yml"),
        grain=grain,
        metrics=(
            {"name": "total_revenue", "type": "sum", "column": "revenue"},
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
