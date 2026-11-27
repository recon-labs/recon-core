import ast
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

import recon_core.adapters as adapters_module
import recon_core.adapters.default_renderers as default_renderers_module
import recon_core.services.run as run_service_module
from recon_core.adapters import (
    AdapterRegistry,
)
from recon_core.artifacts import CompiledCheckLoader, CompiledContractLoader
from recon_core.check_engine import CheckReason, CheckResult, CheckStatus, ContractResult, RunResult
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
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
    assert (outcome.plan is not None) == (failure in {"setup", "engine"})
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


@pytest.mark.regression_capture("run-invocation-identity-timing")
@pytest.mark.parametrize(
    ("status", "category", "lifecycle"),
    [
        (CheckStatus.PASS, ExitCategory.SUCCESS, "completed"),
        (CheckStatus.FAIL, ExitCategory.CHECK_FAILURE, "completed"),
        (CheckStatus.WARN, ExitCategory.SUCCESS, "completed"),
        (CheckStatus.ERROR, ExitCategory.RUNTIME_ERROR, "failed"),
        (CheckStatus.SKIPPED, ExitCategory.SUCCESS, "completed"),
        (CheckStatus.BLOCKED, ExitCategory.RUNTIME_ERROR, "failed"),
        (CheckStatus.NOT_EXECUTABLE, ExitCategory.RUNTIME_ERROR, "failed"),
        (None, ExitCategory.RUNTIME_ERROR, "failed"),
    ],
)
def test_run_invocation_preserves_outcome_and_private_values(
    tmp_path: Path, status: CheckStatus | None, category: ExitCategory, lifecycle: str
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    reason = {
        CheckStatus.SKIPPED: CheckReason.SKIPPED_BY_POLICY,
        CheckStatus.BLOCKED: CheckReason.PREREQUISITE_MISSING,
        CheckStatus.NOT_EXECUTABLE: CheckReason.MISSING_ENGINE_CAPABILITY,
    }.get(status)
    contracts: tuple[ContractResult, ...] = ()
    if status is not None:
        executed = status in {CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.WARN}
        source_value = 123456789 if executed else None
        target_value = 123456788 if status is CheckStatus.FAIL else source_value
        check = CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=status,
            executed=executed,
            reason_code=reason,
            message="Check did not execute." if reason is not None else None,
            blocked_by=("missing-check",) if status is CheckStatus.BLOCKED else (),
            source_value=source_value,
            target_value=target_value,
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_OUTCOME",
                    severity=DiagnosticSeverity.ERROR,
                    message="Test outcome.",
                ),
            )
            if not executed
            else (),
        )
        contracts = (
            ContractResult.from_check_results(
                contract_name="customer_revenue", check_results=(check,)
            ),
        )

    class OutcomeEngine:
        def run(self, *args: Any, **kwargs: Any) -> RunResult:
            return RunResult.from_contract_results(
                run_id=kwargs["run_id"],
                project_name=kwargs["project_name"],
                started_at=kwargs["started_at"],
                finished_at="2026-11-27T10:00:00Z",
                contract_results=contracts,
            )

    outcome = RunService(start_path=tmp_path, engine=OutcomeEngine())._execute_invocation()

    assert outcome.status.value == lifecycle
    assert outcome.service_result.exit_category is category
    assert outcome.run_result is not None
    assert outcome.run_result.status.value == (status.value if status is not None else "no_checks")
    assert outcome.run_result.run_id == outcome.run_id
    assert outcome.run_result.finished_at == outcome.finished_at
    assert outcome.elapsed_ns >= 0
    assert "123456789" not in repr(outcome)
    assert "123456789" not in repr(outcome.service_result.to_dict())
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_invocation_utc_label_preserves_subsecond_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedClock:
        @staticmethod
        def now(tz: Any) -> datetime:
            assert tz is UTC
            return datetime(2026, 11, 27, 10, 0, 0, 123456, tzinfo=UTC)

    monkeypatch.setattr(run_service_module, "datetime", FixedClock)
    assert run_service_module._utc_timestamp() == "2026-11-27T10:00:00.123456Z"


@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_invocation_plan_preserves_loaded_order_and_dependencies(tmp_path: Path) -> None:
    write_project(tmp_path)
    first = _compiled_check_payload(check_id="first", name="first")
    second = _compiled_check_payload(check_id="second", name="second")
    first["prerequisites"] = ["second"]
    write_compiled_checks(tmp_path, contract_name="alpha", checks=[first, second])
    write_compiled_contract(tmp_path, contract_name="alpha")
    write_compiled_checks(tmp_path, contract_name="empty", checks=[])
    write_compiled_contract(tmp_path, contract_name="empty")
    last = _compiled_check_payload(check_id="last", name="last")
    write_compiled_checks(tmp_path, contract_name="zeta", checks=[last])
    write_compiled_contract(
        tmp_path,
        contract_name="zeta",
        source_relation=None,
        source_query="select 'private-query-canary'",
    )

    outcome = RunService(start_path=tmp_path)._execute_invocation()

    plan = outcome.plan
    assert plan is not None
    assert plan.project_name == "ecommerce_recon"
    assert plan.scope.value == "whole_compiled"
    assert tuple(c.contract_name for c in plan.contracts) == ("alpha", "empty", "zeta")
    assert tuple(c.contract_id for c in plan.contracts) == (
        "contract.ecommerce_recon.alpha",
        "contract.ecommerce_recon.empty",
        "contract.ecommerce_recon.zeta",
    )
    assert plan.contracts[1].checks == ()
    checks = plan.contracts[0].checks
    assert tuple(c.check_id for c in checks) == ("first", "second")
    assert checks[0].plan_id == "plan.ecommerce_recon.customer_revenue.first"
    assert checks[0].prerequisites == ("second",)
    assert checks[1].prerequisites == ()
    assert plan.contracts[2].checks[0].check_id == "last"
    with pytest.raises(FrozenInstanceError):
        checks[0].check_id = "changed"
    assert "private-query-canary" not in repr(plan)
    assert str(tmp_path) not in repr(plan)
    assert outcome.run_result is not None
    assert tuple(c.contract_name for c in outcome.run_result.contract_results) == (
        "alpha",
        "empty",
        "zeta",
    )
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize(
    "invalid",
    [
        "missing_checks",
        "missing_contract",
        "malformed",
        "unsupported_version",
        "mismatched_reference",
        "foreign_project",
        "duplicate_check",
        "duplicate_contract",
        "empty",
    ],
)
@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_invalid_compiled_scope_never_reaches_runtime_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    checks = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    contract = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    if invalid == "missing_checks":
        checks.unlink()
    elif invalid == "missing_contract":
        contract.unlink()
    elif invalid == "malformed":
        checks.write_text("invalid: [private-query-canary", encoding="utf-8")
    elif invalid == "unsupported_version":
        payload = yaml.safe_load(checks.read_text(encoding="utf-8"))
        payload["artifact_version"] = 999
        checks.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif invalid == "mismatched_reference":
        payload = yaml.safe_load(contract.read_text(encoding="utf-8"))
        payload["contract"]["id"] = "contract.other"
        contract.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif invalid == "foreign_project":
        for path in (checks, contract):
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["project"]["name"] = "other_project"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif invalid == "duplicate_check":
        payload = yaml.safe_load(checks.read_text(encoding="utf-8"))
        payload["checks"].append(payload["checks"][0])
        checks.write_text(yaml.safe_dump(payload), encoding="utf-8")
    elif invalid == "duplicate_contract":
        (checks.parent / "copy.yml").write_bytes(checks.read_bytes())
    elif invalid == "empty":
        write_compiled_checks(tmp_path, checks=[])

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Invalid artifacts must stop before runtime setup.")

    monkeypatch.setattr(run_service_module, "_prepare_runtime_execution_dependencies", forbidden)
    outcome = RunService(start_path=tmp_path)._execute_invocation()

    assert outcome.plan is None
    assert outcome.run_result is None
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert outcome.service_result.diagnostics
    assert "private-query-canary" not in repr(outcome.service_result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_invocation_plan_does_not_claim_authored_freshness(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    project = tmp_path / "recon_project.yml"
    project.write_text(
        project.read_text(encoding="utf-8").replace("0.1.0", "0.2.0"), encoding="utf-8"
    )
    authored = tmp_path / "contracts" / "customer_revenue.yml"
    authored.parent.mkdir()
    authored.write_text("invalid: [private-authored-canary", encoding="utf-8")
    loaded = CompiledCheckLoader().load(tmp_path / "target")
    assert loaded.succeeded
    matched = CompiledContractLoader().load_for_compiled_checks(tmp_path / "target", loaded.artifacts)
    assert matched.succeeded
    before = {path: path.read_bytes() for path in (tmp_path / "target").rglob("*.yml")}

    outcome = RunService(start_path=tmp_path, engine=_CapturingPassEngine())._execute_invocation()

    assert outcome.plan is not None
    assert outcome.plan.contracts[0].project_version == "0.1.0"
    assert outcome.service_result.exit_category is ExitCategory.SUCCESS
    assert {path: path.read_bytes() for path in before} == before
    _assert_no_runtime_outputs(tmp_path)
