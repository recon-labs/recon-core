from pathlib import Path
from typing import cast

import pytest
import yaml

from recon_core.artifacts import (
    CompiledContractLoader,
    CompiledContractWriter,
    LoadedCompiledChecksArtifact,
)
from recon_core.compiler.models import (
    CompiledArtifactType,
    CompiledContractArtifact,
    CompiledContractReference,
    CompiledEndpoint,
    CompiledProject,
)


def test_loader_loads_compiled_contract_artifact_written_by_writer(tmp_path: Path) -> None:
    artifact = _compiled_contract_artifact()
    CompiledContractWriter().write(artifact, tmp_path / "target")

    result = CompiledContractLoader().load(tmp_path / "target")

    assert result.succeeded
    assert result.diagnostics == ()
    assert len(result.artifacts) == 1
    loaded_artifact = result.artifacts[0]
    assert loaded_artifact.path == (
        tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    )
    assert loaded_artifact.project_name == "ecommerce_recon"
    assert loaded_artifact.project_version == "0.1.0"
    assert loaded_artifact.contract_id == "contract.ecommerce_recon.customer_revenue"
    assert loaded_artifact.contract_name == "customer_revenue"
    assert loaded_artifact.source_file == "contracts/customer_revenue.yml"
    assert loaded_artifact.source.connection == "legacy"
    assert loaded_artifact.source.relation == "qa.customer_source"
    assert loaded_artifact.source.query is None
    assert loaded_artifact.target.connection == "warehouse"
    assert loaded_artifact.target.relation == "qa.customer_target"
    assert loaded_artifact.target.query is None
    assert loaded_artifact.grain_keys == ("customer_id",)
    assert loaded_artifact.diagnostics == ()


def test_loader_preserves_query_endpoint_metadata_without_executing(
    tmp_path: Path,
) -> None:
    payload = _compiled_contract_payload()
    payload["source"] = {
        "connection": "legacy",
        "relation": None,
        "query": "select * from source_table",
    }
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert result.succeeded
    assert result.artifacts[0].source.relation is None
    assert result.artifacts[0].source.query == "select * from source_table"


def test_loader_preserves_safe_diagnostics(tmp_path: Path) -> None:
    payload = _compiled_contract_payload(
        diagnostics=[
            {
                "code": "RC_VALIDATE_EXAMPLE",
                "severity": "error",
                "message": "Compiled contract contains a validation diagnostic.",
                "resource_type": "contract",
                "resource_name": "customer_revenue",
                "path": "contracts/customer_revenue.yml",
                "line": None,
                "column": None,
                "hint": "Fix the contract.",
            }
        ]
    )
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert result.succeeded
    assert [diagnostic.code for diagnostic in result.artifacts[0].diagnostics] == [
        "RC_VALIDATE_EXAMPLE"
    ]


def test_loader_reports_missing_compiled_contracts_directory(tmp_path: Path) -> None:
    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
    assert diagnostic.severity.value == "error"
    assert "compiled-contract artifacts are missing" in diagnostic.message
    assert diagnostic.path == str(tmp_path / "target" / "compiled_contracts")


def test_loader_reports_empty_compiled_contracts_directory(tmp_path: Path) -> None:
    (tmp_path / "target" / "compiled_contracts").mkdir(parents=True)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
    assert diagnostic.path == str(tmp_path / "target" / "compiled_contracts")


def test_loader_reports_missing_referenced_compiled_contract(tmp_path: Path) -> None:
    (tmp_path / "target" / "compiled_contracts").mkdir(parents=True)

    result = CompiledContractLoader().load_for_compiled_checks(
        tmp_path / "target",
        (_loaded_check_artifact(),),
    )

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
    assert diagnostic.path == str(
        tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    )


def test_loader_rejects_symlinked_compiled_contracts_path_component(
    tmp_path: Path,
) -> None:
    external_target = tmp_path / "external_target"
    _write_payload(
        external_target / "compiled_contracts" / "customer_revenue.yml",
        _compiled_contract_payload(),
    )
    try:
        (tmp_path / "target").symlink_to(external_target, target_is_directory=True)
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(tmp_path / "target" / "compiled_contracts")
    assert "symlink" in diagnostic.message


def test_loader_rejects_symlinked_compiled_contract_artifact_file(
    tmp_path: Path,
) -> None:
    compiled_contracts_dir = tmp_path / "target" / "compiled_contracts"
    compiled_contracts_dir.mkdir(parents=True)
    external_artifact = tmp_path / "external" / "customer_revenue.yml"
    _write_payload(external_artifact, _compiled_contract_payload())
    artifact_path = compiled_contracts_dir / "customer_revenue.yml"
    try:
        artifact_path.symlink_to(external_artifact)
    except OSError:
        pytest.skip("Filesystem does not support file symlinks.")

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(artifact_path)
    assert "symlink" in diagnostic.message


def test_loader_rejects_dangling_symlinked_referenced_compiled_contract_artifact(
    tmp_path: Path,
) -> None:
    compiled_contracts_dir = tmp_path / "target" / "compiled_contracts"
    compiled_contracts_dir.mkdir(parents=True)
    artifact_path = compiled_contracts_dir / "customer_revenue.yml"
    try:
        artifact_path.symlink_to(tmp_path / "missing" / "customer_revenue.yml")
    except OSError:
        pytest.skip("Filesystem does not support file symlinks.")

    result = CompiledContractLoader().load_for_compiled_checks(
        tmp_path / "target",
        (_loaded_check_artifact(),),
    )

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(artifact_path)
    assert "symlink" in diagnostic.message


@pytest.mark.regression_capture("compiled-artifact-yaml-loader-diagnostics")
def test_loader_reports_invalid_yaml_without_raw_artifact_content(tmp_path: Path) -> None:
    artifact_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        "artifact_type: compiled_contract\nsecret_token: [super-secret\n",
        encoding="utf-8",
    )

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(artifact_path)
    assert diagnostic.message == "Compiled-contract artifact is invalid YAML."
    assert "super-secret" not in diagnostic.to_dict()["message"]


@pytest.mark.regression_capture("compiled-artifact-yaml-loader-diagnostics")
def test_loader_rejects_duplicate_yaml_keys_in_compiled_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        """
artifact_type: compiled_contract
artifact_version: 1
recon_version: 0.0.test
generated_at: 2026-05-23T12:00:00Z
invocation_id: 01JTESTINVOCATION0000000000
project:
  name: ecommerce_recon
  version: 0.1.0
contract:
  id: contract.ecommerce_recon.customer_revenue
  name: customer_revenue
  source_file: contracts/customer_revenue.yml
source:
  connection: legacy
  relation: qa.customer_source
  relation: qa.customer_source_duplicate
target:
  connection: warehouse
  relation: qa.customer_target
  query: null
identity:
  grain:
    keys:
      - customer_id
  cdc: null
diagnostics: []
""".lstrip(),
        encoding="utf-8",
    )

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.message == "Compiled-contract artifact is invalid YAML."


def test_loader_rejects_non_string_root_mapping_keys(tmp_path: Path) -> None:
    payload = cast(dict[object, object], dict(_compiled_contract_payload()))
    payload[1] = "boom"
    artifact_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert "artifact root" in diagnostic.message
    assert "string keys" in diagnostic.message
    assert "boom" not in diagnostic.message


def test_loader_reports_wrong_artifact_type_and_version(tmp_path: Path) -> None:
    payload = _compiled_contract_payload()
    payload["artifact_type"] = "compiled_checks"
    _write_payload(tmp_path / "target" / "compiled_contracts" / "wrong_type.yml", payload)

    payload = _compiled_contract_payload(contract_name="wrong_version")
    payload["artifact_version"] = 999
    _write_payload(tmp_path / "target" / "compiled_contracts" / "wrong_version.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID",
        "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID",
    ]
    assert "artifact_type" in result.diagnostics[0].message
    assert "artifact_version" in result.diagnostics[1].message


def test_loader_rejects_boolean_artifact_version(tmp_path: Path) -> None:
    payload = _compiled_contract_payload()
    payload["artifact_version"] = True
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert "artifact_version" in diagnostic.message


@pytest.mark.parametrize("field", ["source", "target", "identity"])
def test_loader_reports_missing_required_contract_fields(tmp_path: Path, field: str) -> None:
    payload = _compiled_contract_payload()
    del payload[field]
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert field in diagnostic.message


@pytest.mark.parametrize(
    "source",
    [
        {"connection": "legacy", "relation": None, "query": None},
        {
            "connection": "legacy",
            "relation": "qa.customer_source",
            "query": "select * from customer_source",
        },
    ],
)
def test_loader_rejects_invalid_endpoint_shape(
    tmp_path: Path,
    source: dict[str, object],
) -> None:
    payload = _compiled_contract_payload()
    payload["source"] = source
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert "exactly one" in diagnostic.message


def test_loader_rejects_empty_grain_key_value(tmp_path: Path) -> None:
    payload = _compiled_contract_payload()
    identity = cast(dict[str, object], payload["identity"])
    grain = cast(dict[str, object], identity["grain"])
    grain["keys"] = ["customer_id", ""]
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert "identity.grain.keys[1]" in diagnostic.message


def test_loader_rejects_duplicate_contract_identity(tmp_path: Path) -> None:
    _write_payload(
        tmp_path / "target" / "compiled_contracts" / "aaa.yml",
        _compiled_contract_payload(contract_name="customer_revenue"),
    )
    payload = _compiled_contract_payload(contract_name="orders_revenue")
    contract = cast(dict[str, object], payload["contract"])
    contract["id"] = "contract.ecommerce_recon.customer_revenue"
    _write_payload(tmp_path / "target" / "compiled_contracts" / "bbb.yml", payload)

    result = CompiledContractLoader().load(tmp_path / "target")

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert "duplicate contract id" in diagnostic.message


def test_loader_rejects_compiled_check_contract_reference_mismatch(tmp_path: Path) -> None:
    payload = _compiled_contract_payload()
    contract = cast(dict[str, object], payload["contract"])
    contract["id"] = "contract.ecommerce_recon.other_customer_revenue"
    _write_payload(tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml", payload)

    result = CompiledContractLoader().load_for_compiled_checks(
        tmp_path / "target",
        (_loaded_check_artifact(),),
    )

    assert not result.succeeded
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(
        tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    )
    assert "does not match" in diagnostic.message


def test_loader_rejects_unsafe_compiled_check_contract_reference(tmp_path: Path) -> None:
    payload = _compiled_contract_payload(contract_name="../escaped_contract")
    _write_payload(tmp_path / "target" / "escaped_contract.yml", payload)
    (tmp_path / "target" / "compiled_contracts").mkdir(parents=True)

    result = CompiledContractLoader().load_for_compiled_checks(
        tmp_path / "target",
        (_loaded_check_artifact(contract_name="../escaped_contract"),),
    )

    assert not result.succeeded
    assert result.artifacts == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"
    assert diagnostic.path == str(Path("target") / "compiled_checks" / "../escaped_contract.yml")
    assert "unsafe compiled contract reference" in diagnostic.message
    assert "../escaped_contract" not in diagnostic.message


def _compiled_contract_artifact(
    contract_name: str = "customer_revenue",
) -> CompiledContractArtifact:
    return CompiledContractArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CONTRACT,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id=f"contract.ecommerce_recon.{contract_name}",
            name=contract_name,
            source_file=f"contracts/{contract_name}.yml",
            authored_version=1,
        ),
        source=CompiledEndpoint(
            connection="legacy",
            relation="qa.customer_source",
        ),
        target=CompiledEndpoint(
            connection="warehouse",
            relation="qa.customer_target",
        ),
        grain_keys=("customer_id",),
    )


def _compiled_contract_payload(
    *,
    contract_name: str = "customer_revenue",
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "artifact_type": "compiled_contract",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
            "authored_version": 1,
        },
        "source": {
            "connection": "legacy",
            "relation": "qa.customer_source",
            "query": None,
        },
        "target": {
            "connection": "warehouse",
            "relation": "qa.customer_target",
            "query": None,
        },
        "identity": {
            "grain": {
                "keys": ["customer_id"],
            },
            "cdc": None,
        },
        "columns": None,
        "metrics": [],
        "policies": {
            "sampling": None,
            "tolerance_policy": None,
            "nulls": None,
            "schema": None,
            "cdc": None,
            "evidence": None,
        },
        "diagnostics": diagnostics if diagnostics is not None else [],
    }


def _loaded_check_artifact(
    *,
    contract_name: str = "customer_revenue",
) -> LoadedCompiledChecksArtifact:
    return LoadedCompiledChecksArtifact(
        path=Path("target") / "compiled_checks" / f"{contract_name}.yml",
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contract_id=f"contract.ecommerce_recon.{contract_name}",
        contract_name=contract_name,
        source_file=f"contracts/{contract_name}.yml",
        checks=(),
    )


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
