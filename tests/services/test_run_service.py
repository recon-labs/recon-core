import ast
from pathlib import Path
from typing import Any

import pytest

import recon_core.adapters as adapters_module
import recon_core.adapters.default_renderers as default_renderers_module
import recon_core.services.run as run_service_module
from recon_core.adapters import (
    AdapterRegistry,
)
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    RecordingDuckDbFactory,
    _assert_no_runtime_outputs,
    _CapturingPassEngine,
    _compiled_check_payload,
    _FailingEngine,
    _RaisingEngine,
    row_count_plan,
    write_compiled_checks,
    write_compiled_contract,
    write_profiles,
    write_project,
)


def _imported_modules_from(module_file: str | None) -> set[str]:
    assert module_file is not None
    source = Path(module_file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules


def _top_level_imported_modules_from(module_file: str | None) -> set[str]:
    assert module_file is not None
    source = Path(module_file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules


def test_run_service_uses_neutral_runtime_safety_boundary() -> None:
    imported_modules = _imported_modules_from(run_service_module.__file__)

    assert not any(module.startswith("recon_core.adapters.duckdb") for module in imported_modules)
    assert "recon_core.adapters.default_renderers" in imported_modules
    assert "recon_core.adapters.runtime_safety" in imported_modules


def test_default_runtime_renderer_helper_stays_internal_and_lazy() -> None:
    imported_modules = _top_level_imported_modules_from(default_renderers_module.__file__)

    assert "default_runtime_renderers_by_adapter_type" not in adapters_module.__all__
    assert not any(module.startswith("recon_core.adapters.duckdb") for module in imported_modules)


def test_run_service_provides_default_duckdb_renderer_in_execution_context(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", RecordingDuckDbFactory())
    engine = _CapturingPassEngine()

    result = RunService(
        start_path=tmp_path,
        adapter_registry=registry,
        engine=engine,
    ).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert engine.execution_context is not None
    renderer = engine.execution_context.renderers_by_adapter_type.get("duckdb")
    assert renderer is not None
    assert getattr(renderer, "adapter_type", None) == "duckdb"
    _assert_no_runtime_outputs(tmp_path)


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
    write_compiled_contract(tmp_path)

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


def test_run_service_does_not_mutate_preexisting_run_outputs(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    output_contents = {
        tmp_path / "target" / "run_results.json": '{"status":"stale"}\n',
        tmp_path / "target" / "failures" / "existing.csv": "id\n1\n",
        tmp_path / "reports" / "existing.md": "# stale report\n",
        tmp_path / "state" / "existing.json": '{"watermark":"stale"}\n',
    }
    for path, content in output_contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    for path, content in output_contents.items():
        assert path.read_text(encoding="utf-8") == content


def test_run_service_uses_compiled_artifacts_without_parsing_authored_contracts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
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


def test_run_service_runs_valid_artifacts_when_another_artifact_has_empty_checks(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path, contract_name="valid_contract")
    write_compiled_contract(tmp_path, contract_name="valid_contract")
    write_compiled_checks(
        tmp_path,
        contract_name="empty_contract",
        checks=[],
        diagnostics=[
            {
                "code": "RC_VALIDATE_NO_COMPILED_CHECKS",
                "severity": "error",
                "message": "Contract does not compile into any checks.",
                "resource_type": "contract",
                "resource_name": "empty_contract",
                "path": "contracts/empty_contract.yml",
                "line": None,
                "column": None,
                "hint": "Add a supported check pack or metric.",
            }
        ],
    )
    write_compiled_contract(tmp_path, contract_name="empty_contract")

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_NO_COMPILED_CHECKS",
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY",
    ]


def test_run_service_maps_engine_check_failure_to_check_failure_exit(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    result = RunService(start_path=tmp_path, engine=_FailingEngine()).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert result.diagnostics == ()


def test_run_service_sanitizes_engine_boundary_exception(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    result = RunService(start_path=tmp_path, engine=_RaisingEngine()).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"
    ]
    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )
    assert "super-secret" not in diagnostic_text
    assert "traceback" not in diagnostic_text.lower()


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_run_service_clock_surrounds_preparation_and_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    events: list[str] = []
    labels = iter(("2026-11-27T10:00:00.123Z", "2026-11-27T10:00:02.456Z"))
    received: dict[str, Any] = {}
    original_load = run_service_module.load_project_context

    def timestamp() -> str:
        events.append("timestamp")
        return next(labels)

    def load(*args: Any, **kwargs: Any) -> Any:
        events.append("project")
        return original_load(*args, **kwargs)

    class RecordingEngine(_CapturingPassEngine):
        def run(self, *args: Any, **kwargs: Any) -> Any:
            events.append("engine")
            received.update(kwargs)
            return super().run(*args, **kwargs)

    monkeypatch.setattr(run_service_module, "_utc_timestamp", timestamp)
    monkeypatch.setattr(run_service_module, "load_project_context", load)
    result = RunService(start_path=tmp_path, engine=RecordingEngine()).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert events == ["timestamp", "project", "engine", "timestamp"]
    assert received["started_at"] == "2026-11-27T10:00:00.123Z"
    assert received["finished_at"] is None


@pytest.mark.parametrize(
    ("failure", "stage", "category"),
    [
        ("project", "project_configuration", ExitCategory.CONFIGURATION_ERROR),
        ("checks", "compiled_checks", ExitCategory.RUNTIME_ERROR),
        ("empty", "compiled_checks", ExitCategory.RUNTIME_ERROR),
        ("contracts", "compiled_contracts", ExitCategory.RUNTIME_ERROR),
        ("setup", "runtime_setup", ExitCategory.CONFIGURATION_ERROR),
        ("engine", "check_execution", ExitCategory.RUNTIME_ERROR),
    ],
)
@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_run_invocation_retains_identity_on_early_failure(
    tmp_path: Path, failure: str, stage: str, category: ExitCategory
) -> None:
    if failure != "project":
        write_project(tmp_path, profile="missing" if failure == "setup" else None)
    if failure in {"empty", "contracts", "setup", "engine"}:
        write_compiled_checks(
            tmp_path,
            checks=[]
            if failure == "empty"
            else [_compiled_check_payload(operations=row_count_plan())]
            if failure == "setup"
            else None,
        )
    if failure in {"setup", "engine"}:
        write_compiled_contract(tmp_path)
    service = RunService(start_path=tmp_path, engine=_RaisingEngine())

    outcome = service._execute_invocation()
    another = service._execute_invocation()

    assert outcome.run_id.startswith("run-") and len(outcome.run_id) == 36
    assert outcome.run_id != another.run_id
    assert outcome.project_name == (None if failure == "project" else "ecommerce_recon")
    assert outcome.stage.value == stage
    assert outcome.status.value == "failed"
    assert outcome.run_result is None
    assert outcome.elapsed_ns >= 0
    assert outcome.started_at.endswith("Z") and outcome.finished_at.endswith("Z")
    assert outcome.service_result.exit_category is category
    assert outcome.service_result.to_dict() == service.execute().to_dict()
    assert "super-secret" not in repr(outcome)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_run_invocation_elapsed_survives_wall_clock_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    labels = iter(("2026-11-27T10:00:01.123Z", "2026-11-27T09:59:59.456Z"))
    ticks = iter((1_000_000_000, 1_250_000_000))
    monkeypatch.setattr(run_service_module, "_utc_timestamp", lambda: next(labels))
    monkeypatch.setattr(run_service_module, "monotonic_ns", lambda: next(ticks))

    outcome = RunService(start_path=tmp_path, engine=_CapturingPassEngine())._execute_invocation()

    assert outcome.status.value == "completed"
    assert outcome.started_at == "2026-11-27T10:00:01.123Z"
    assert outcome.finished_at == "2026-11-27T09:59:59.456Z"
    assert outcome.elapsed_ns == 250_000_000
    assert outcome.run_result is not None
    assert outcome.run_result.run_id == outcome.run_id
    assert outcome.run_result.started_at == outcome.started_at
    assert outcome.run_result.finished_at == outcome.finished_at
    assert outcome.service_result.exit_category is ExitCategory.SUCCESS
    assert set(outcome.service_result.to_dict()) == {
        "exit_category",
        "exit_code",
        "message",
        "diagnostics",
    }
    _assert_no_runtime_outputs(tmp_path)
