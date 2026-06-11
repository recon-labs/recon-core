from pathlib import Path

import pytest
import yaml

from recon_core.artifacts import CompiledCheckLoader, CompiledCheckWriter
from recon_core.compiler.models import (
    CheckOrigin,
    CheckOriginKind,
    CheckPlan,
    CheckRequirements,
    CompiledArtifactType,
    CompiledCheck,
    CompiledChecksArtifact,
    CompiledCheckType,
    CompiledContractReference,
    CompiledProject,
    Identity,
    IdentityKind,
    OperationSide,
    TypedOperation,
)


def test_loader_loads_compiled_check_artifact_written_by_writer(tmp_path: Path) -> None:
    artifact = _compiled_checks_artifact()
    CompiledCheckWriter().write(artifact, tmp_path / "target")

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert result.succeeded
    assert result.diagnostics == ()
    assert len(result.artifacts) == 1
    loaded_artifact = result.artifacts[0]
    assert loaded_artifact.path == tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    assert loaded_artifact.project_name == "ecommerce_recon"
    assert loaded_artifact.project_version == "0.1.0"
    assert loaded_artifact.contract_name == "customer_revenue"
    assert loaded_artifact.contract_id == "contract.ecommerce_recon.customer_revenue"
    assert loaded_artifact.source_file == "contracts/customer_revenue.yml"
    assert loaded_artifact.diagnostics == ()

    loaded_check = loaded_artifact.checks[0]
    assert loaded_check.id == "check.ecommerce_recon.customer_revenue.row_count_diff"
    assert loaded_check.name == "row_count_diff"
    assert loaded_check.check_type == "row_count_diff"
    assert loaded_check.contract_name == "customer_revenue"
    assert loaded_check.prerequisites == ()
    assert loaded_check.plan.id == "plan.ecommerce_recon.customer_revenue.row_count_diff"
    assert loaded_check.plan.operations == ({"type": "row_count", "side": "source"},)
    assert loaded_check.plan.required_capabilities == ()


def test_loader_preserves_unknown_check_type_and_operation_for_dispatch(
    tmp_path: Path,
) -> None:
    payload = _compiled_checks_payload(
        checks=[
            _compiled_check_payload(
                check_type="future_value_match",
                operations=[{"type": "future_operation", "custom": "metadata"}],
            )
        ]
    )
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert result.succeeded
    loaded_check = result.artifacts[0].checks[0]
    assert loaded_check.check_type == "future_value_match"
    assert loaded_check.plan.operations == ({"type": "future_operation", "custom": "metadata"},)


def test_loader_reports_missing_compiled_checks_directory(tmp_path: Path) -> None:
    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND"
    assert diagnostic.severity.value == "error"
    assert "compiled-check artifacts are missing" in diagnostic.message
    assert diagnostic.path == str(tmp_path / "target" / "compiled_checks")


def test_loader_reports_empty_compiled_checks_directory(tmp_path: Path) -> None:
    (tmp_path / "target" / "compiled_checks").mkdir(parents=True)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_NO_COMPILED_CHECKS"
    assert diagnostic.path == str(tmp_path / "target" / "compiled_checks")


def test_loader_reports_invalid_yaml_without_raw_artifact_content(tmp_path: Path) -> None:
    artifact_path = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        "artifact_type: compiled_checks\nsecret_token: [super-secret\n",
        encoding="utf-8",
    )

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert diagnostic.path == str(artifact_path)
    assert diagnostic.message == "Compiled-check artifact is invalid YAML."
    assert "super-secret" not in diagnostic.to_dict()["message"]


def test_loader_reports_wrong_artifact_type_and_version(tmp_path: Path) -> None:
    payload = _compiled_checks_payload()
    payload["artifact_type"] = "compiled_contract"
    _write_payload(tmp_path / "target" / "compiled_checks" / "wrong_type.yml", payload)

    payload = _compiled_checks_payload(contract_name="wrong_version")
    payload["artifact_version"] = 999
    _write_payload(tmp_path / "target" / "compiled_checks" / "wrong_version.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID",
        "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID",
    ]
    assert "artifact_type" in result.diagnostics[0].message
    assert "artifact_version" in result.diagnostics[1].message


def test_loader_rejects_boolean_artifact_version(tmp_path: Path) -> None:
    payload = _compiled_checks_payload()
    payload["artifact_version"] = True
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert "artifact_version" in diagnostic.message


def test_loader_reports_missing_required_fields(tmp_path: Path) -> None:
    payload = _compiled_checks_payload()
    del payload["contract"]
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert "contract" in diagnostic.message


def test_loader_reports_empty_checks_scope(tmp_path: Path) -> None:
    payload = _compiled_checks_payload(checks=[])
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_NO_COMPILED_CHECKS"
    assert diagnostic.path == str(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml")


def test_loader_reports_duplicate_check_ids(tmp_path: Path) -> None:
    check = _compiled_check_payload()
    payload = _compiled_checks_payload(checks=[check, dict(check)])
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert "duplicate check id" in diagnostic.message


@pytest.mark.parametrize(
    ("identity", "expected_message"),
    [
        (None, "checks[0].identity"),
        ({"kind": "banana", "keys": []}, "checks[0].identity.kind"),
        ({"kind": "none"}, "checks[0].identity.keys"),
    ],
)
def test_loader_reports_malformed_check_identity_payloads(
    tmp_path: Path,
    identity: dict[str, object] | None,
    expected_message: str,
) -> None:
    check = _compiled_check_payload()
    if identity is None:
        del check["identity"]
    else:
        check["identity"] = identity
    payload = _compiled_checks_payload(checks=[check])
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert expected_message in diagnostic.message


def test_loader_reports_malformed_operation_payload(tmp_path: Path) -> None:
    payload = _compiled_checks_payload(
        checks=[_compiled_check_payload(operations=[{"side": "source"}])]
    )
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert "plan.operations[0].type" in diagnostic.message


@pytest.mark.parametrize(
    ("operations", "expected_message"),
    [
        ([{"type": "row_count"}], "plan.operations[0].side"),
        ([{"type": "key_diff", "identity": {"kind": "grain", "keys": ["id"]}}], "direction"),
        ([{"type": "key_diff", "direction": "source_minus_target"}], "identity"),
        (
            [
                {
                    "type": "null_key",
                    "side": "source",
                    "identity": {"kind": "banana", "keys": ["id"]},
                }
            ],
            "plan.operations[0].identity.kind",
        ),
        (
            [{"type": "aggregate", "side": "source", "aggregate": "sum"}],
            "plan.operations[0].column",
        ),
        (
            [
                {
                    "type": "grouped_aggregate",
                    "side": "source",
                    "aggregate": "sum",
                    "column": "revenue",
                    "group_by": [],
                }
            ],
            "plan.operations[0].group_by",
        ),
    ],
)
def test_loader_reports_malformed_known_operation_payloads(
    tmp_path: Path,
    operations: list[dict[str, object]],
    expected_message: str,
) -> None:
    payload = _compiled_checks_payload(checks=[_compiled_check_payload(operations=operations)])
    _write_payload(tmp_path / "target" / "compiled_checks" / "customer_revenue.yml", payload)

    result = CompiledCheckLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
    assert expected_message in diagnostic.message


def _compiled_checks_artifact() -> CompiledChecksArtifact:
    return CompiledChecksArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CHECKS,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id="contract.ecommerce_recon.customer_revenue",
            name="customer_revenue",
            source_file="contracts/customer_revenue.yml",
        ),
        checks=(
            CompiledCheck(
                id="check.ecommerce_recon.customer_revenue.row_count_diff",
                name="row_count_diff",
                check_type=CompiledCheckType.ROW_COUNT_DIFF,
                origin=CheckOrigin(
                    kind=CheckOriginKind.CHECK_PACK,
                    name="recon_core.basic_equivalence",
                ),
                identity=Identity(kind=IdentityKind.NONE),
                requirements=CheckRequirements(),
                plan=CheckPlan(
                    id="plan.ecommerce_recon.customer_revenue.row_count_diff",
                    operations=(TypedOperation.row_count(side=OperationSide.SOURCE),),
                    required_capabilities=(),
                ),
            ),
        ),
    )


def _compiled_checks_payload(
    *,
    contract_name: str = "customer_revenue",
    checks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "artifact_type": "compiled_checks",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
        },
        "checks": checks if checks is not None else [_compiled_check_payload()],
        "diagnostics": [],
    }


def _compiled_check_payload(
    *,
    check_type: str = "row_count_diff",
    operations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": "check.ecommerce_recon.customer_revenue.row_count_diff",
        "name": "row_count_diff",
        "type": check_type,
        "origin": {"kind": "check_pack", "name": "recon_core.basic_equivalence"},
        "identity": {"kind": "none", "keys": []},
        "requirements": {
            "requires_grain_keys": False,
            "requires_non_null_grain": False,
            "requires_unique_grain": False,
            "requires_cdc_keys": False,
            "required_columns": [],
            "required_metrics": [],
            "required_capabilities": [],
        },
        "sampling": {"mode": "full"},
        "tolerance": None,
        "prerequisites": [],
        "blocking_policy": {"on_prerequisite_failure": "skipped"},
        "plan": {
            "id": "plan.ecommerce_recon.customer_revenue.row_count_diff",
            "operations": operations
            if operations is not None
            else [{"type": "row_count", "side": "source"}],
            "required_capabilities": [],
        },
        "rendering": {"status": "not_rendered", "sql_paths": []},
        "diagnostics": [],
    }


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
