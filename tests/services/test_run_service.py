from pathlib import Path

import yaml

from recon_core.artifacts import LoadedCompiledChecksArtifact
from recon_core.check_engine import (
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)
from recon_core.services import RunService
from recon_core.services.results import ExitCategory


def test_run_service_reports_missing_compiled_artifacts(tmp_path: Path) -> None:
    write_project(tmp_path)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compiled-check artifacts could not be loaded."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND"
    ]
    assert not (tmp_path / "target" / "run_results.json").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "state").exists()


def test_run_service_loads_compiled_checks_and_returns_not_executable_status(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]
    assert "row_count" in result.diagnostics[0].message
    assert not (tmp_path / "target" / "run_results.json").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "state").exists()


def test_run_service_uses_compiled_artifacts_without_parsing_authored_contracts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    contract_path = tmp_path / "contracts" / "customer_revenue.yml"
    contract_path.parent.mkdir()
    contract_path.write_text(
        "version: 1\nsource:\n  query: select * from t where ssn: secret\n",
        encoding="utf-8",
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]
    assert "secret" not in "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )


def test_run_service_reports_empty_compiled_check_scope(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path, checks=[])

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "No compiled checks are available."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_NO_COMPILED_CHECKS"
    ]


def test_run_service_maps_engine_check_failure_to_check_failure_exit(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)

    result = RunService(start_path=tmp_path, engine=_FailingEngine()).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert result.diagnostics == ()


def write_project(path: Path) -> None:
    (path / "recon_project.yml").write_text(
        """
name: ecommerce_recon
version: 0.1.0
config-version: 1
contract-paths:
  - contracts
target-path: target
report-path: reports
state-path: state
""".lstrip(),
        encoding="utf-8",
    )


def write_compiled_checks(
    path: Path,
    *,
    checks: list[dict[str, object]] | None = None,
) -> None:
    artifact_path = path / "target" / "compiled_checks" / "customer_revenue.yml"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        yaml.safe_dump(_compiled_checks_payload(checks=checks), sort_keys=False),
        encoding="utf-8",
    )


class _FailingEngine:
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
    ) -> RunResult:
        check_result = CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.FAIL,
            executed=True,
            source_value=10,
            target_value=11,
        )
        contract_result = ContractResult.from_check_results(
            contract_name="customer_revenue",
            check_results=(check_result,),
        )
        return RunResult.from_contract_results(
            run_id=run_id,
            project_name=project_name or artifacts[0].project_name,
            started_at=started_at,
            finished_at=finished_at,
            contract_results=(contract_result,),
        )


def _compiled_checks_payload(
    *,
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
            "id": "contract.ecommerce_recon.customer_revenue",
            "name": "customer_revenue",
            "source_file": "contracts/customer_revenue.yml",
        },
        "checks": checks if checks is not None else [_compiled_check_payload()],
        "diagnostics": [],
    }


def _compiled_check_payload() -> dict[str, object]:
    return {
        "id": "check.ecommerce_recon.customer_revenue.row_count_diff",
        "name": "row_count_diff",
        "type": "row_count_diff",
        "origin": {"kind": "check_pack", "name": "recon_core.basic_equivalence"},
        "identity": {"kind": "none", "keys": []},
        "requirements": {
            "requires_grain_keys": False,
            "requires_non_null_grain": False,
            "requires_unique_grain": False,
            "requires_cdc_keys": False,
            "required_columns": [],
            "required_metrics": [],
            "required_capabilities": ["row_count"],
        },
        "sampling": {"mode": "full"},
        "tolerance": None,
        "prerequisites": [],
        "blocking_policy": {"on_prerequisite_failure": "skipped"},
        "plan": {
            "id": "plan.ecommerce_recon.customer_revenue.row_count_diff",
            "operations": [{"type": "row_count", "side": "source"}],
            "required_capabilities": ["row_count"],
        },
        "rendering": {"status": "not_rendered", "sql_paths": []},
        "diagnostics": [],
    }
