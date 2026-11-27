import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

import recon_core.adapters as adapters_module
import recon_core.adapters.default_renderers as default_renderers_module
import recon_core.services.run as run_service_module
from recon_core._run_control import _RunControl, _RunStoppedError, _StopCause
from recon_core.adapters import (
    AdapterRegistry,
)
from recon_core.artifacts import CompiledCheckLoader, CompiledContractLoader
from recon_core.check_engine import (
    CheckDispatcher,
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)
from recon_core.cli.main import main
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
    assert outcome.scope_facts.planned_check_count == (
        0 if failure == "empty" else 1 if failure in {"setup", "engine"} else None
    )
    assert outcome.scope_facts.planned_contract_count == (
        1 if failure in {"setup", "engine"} else None
    )
    assert outcome.scope_facts.finalized_check_count == 0
    assert outcome.scope_facts.executed_check_count == 0
    assert outcome.scope_facts.complete is (False if failure in {"setup", "engine"} else None)
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
    tmp_path: Path,
    status: CheckStatus | None,
    category: ExitCategory,
    lifecycle: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_project(tmp_path)
    check_id = "check.ecommerce_recon.customer_revenue.private_plan_canary"
    write_compiled_checks(
        tmp_path, checks=[_compiled_check_payload(check_id=check_id, name="private_plan_canary")]
    )
    write_compiled_contract(
        tmp_path,
        source_relation=None,
        source_query="select 'private-query-canary'",
        target_relation="qa.private_relation_canary",
    )
    safe_warning = Diagnostic(
        code="RC_TEST_SAFE_WARNING",
        severity=DiagnosticSeverity.WARNING,
        message="Safe warning message.",
        hint="Safe actionable hint.",
        path="contracts/customer_revenue.yml",
    )
    for relative in (
        "target/run_results.json",
        "target/failures/existing.csv",
        "target/compiled_sql/existing.sql",
        "reports/existing.md",
        "state/existing.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private-existing-output", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
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
            check_id=check_id,
            name="private_plan_canary",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=status,
            executed=executed,
            reason_code=reason,
            message="private-check-message-canary",
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
                contract_name="customer_revenue",
                check_results=(check,),
                diagnostics=(safe_warning,),
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
                diagnostics=(safe_warning,),
            )

    monkeypatch.setattr(run_service_module, "CheckEngine", OutcomeEngine)
    service = RunService(start_path=tmp_path)
    outcome = service._execute_invocation()

    assert outcome.status.value == lifecycle
    assert outcome.service_result.exit_category is category
    assert outcome.run_result is not None
    assert outcome.run_result.status.value == (status.value if status is not None else "no_checks")
    assert outcome.scope_facts.planned_check_count == 1
    assert outcome.scope_facts.finalized_check_count == (0 if status is None else 1)
    assert outcome.scope_facts.executed_check_count == (
        1 if status in {CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.WARN} else 0
    )
    assert outcome.scope_facts.complete is (status is not None)
    assert outcome.run_result.run_id == outcome.run_id
    assert outcome.run_result.finished_at == outcome.finished_at
    assert outcome.elapsed_ns >= 0
    assert outcome.plan is not None
    assert outcome.plan.contracts[0].checks[0].check_id == check_id
    public = service.execute().to_dict()
    assert public == outcome.service_result.to_dict()
    assert set(public) == {"exit_category", "exit_code", "message", "diagnostics"}
    assert public["exit_category"] == category.value
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == public["exit_code"]
    assert public["message"] in cli.output
    if status is not None:
        assert public["diagnostics"].count(safe_warning.to_dict()) == 1
        assert cli.output.count("RC_TEST_SAFE_WARNING") == 1
        assert safe_warning.message in cli.output
        assert safe_warning.hint in cli.output
        assert safe_warning.path in cli.output
    else:
        assert "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR" in cli.output
        assert "RC_TEST_SAFE_WARNING" not in cli.output
    for token in (
        "private_plan_canary",
        "private-query-canary",
        "private_relation_canary",
        "private-check-message-canary",
        "private-existing-output",
        "123456789",
        "123456788",
        str(tmp_path),
    ):
        assert token not in repr(outcome)
        assert token not in repr(public)
        assert token not in cli.output
        assert token not in caplog.text
    assert outcome.run_id not in repr(public)
    assert outcome.run_id not in cli.output
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


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
    assert outcome.scope_facts.planned_contract_count == 3
    assert outcome.scope_facts.planned_check_count == 3
    assert outcome.scope_facts.finalized_check_count == 3
    assert outcome.scope_facts.executed_check_count == 0
    assert outcome.scope_facts.complete is True
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
        "missing_check_directory",
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
    if invalid in {"missing_checks", "missing_check_directory"}:
        checks.unlink()
        if invalid == "missing_check_directory":
            checks.parent.rmdir()
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
    assert outcome.scope_facts.planned_check_count == (
        0 if invalid in {"empty", "missing_checks"} else None
    )
    assert outcome.scope_facts.planned_contract_count is None
    assert outcome.scope_facts.finalized_check_count == 0
    assert outcome.scope_facts.executed_check_count == 0
    assert outcome.scope_facts.complete is None
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
    matched = CompiledContractLoader().load_for_compiled_checks(
        tmp_path / "target", loaded.artifacts
    )
    assert matched.succeeded
    before = {path: path.read_bytes() for path in (tmp_path / "target").rglob("*.yml")}

    outcome = RunService(start_path=tmp_path, engine=_CapturingPassEngine())._execute_invocation()

    assert outcome.plan is not None
    assert outcome.plan.contracts[0].project_version == "0.1.0"
    assert outcome.service_result.exit_category is ExitCategory.SUCCESS
    assert {path: path.read_bytes() for path in before} == before
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-preparation-and-diagnostic-identity")
@pytest.mark.parametrize(
    ("stage", "plan_known", "diagnostic_code"),
    [
        ("project_configuration", False, "RC_RUNTIME_RUN_INTERNAL_ERROR"),
        ("compiled_checks", False, "RC_RUNTIME_RUN_INTERNAL_ERROR"),
        ("compiled_contracts", False, "RC_RUNTIME_RUN_INTERNAL_ERROR"),
        ("runtime_setup", True, "RC_RUNTIME_RUN_INTERNAL_ERROR"),
        ("check_execution", True, "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"),
        ("result_projection", True, "RC_RUNTIME_RUN_INTERNAL_ERROR"),
    ],
)
def test_unexpected_invocation_failure_is_finalized_without_private_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    plan_known: bool,
    diagnostic_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("private-preparation-error password=super-secret")

    if stage == "project_configuration":
        monkeypatch.setattr(run_service_module, "load_project_context", fail)
    elif stage == "compiled_checks":
        monkeypatch.setattr(CompiledCheckLoader, "load", fail)
    elif stage == "compiled_contracts":
        monkeypatch.setattr(CompiledContractLoader, "_load_for_runtime", fail)
    elif stage == "runtime_setup":
        monkeypatch.setattr(run_service_module, "_prepare_runtime_execution_dependencies", fail)
    else:
        monkeypatch.setattr(run_service_module, "_run_service_result", fail)

    engine = _RaisingEngine() if stage == "check_execution" else _CapturingPassEngine()
    monkeypatch.setattr(run_service_module, "CheckEngine", lambda: engine)
    service = RunService(start_path=tmp_path)
    outcome = service._execute_invocation()

    assert outcome.run_id.startswith("run-")
    assert outcome.stage.value == stage
    assert outcome.status.value == "failed"
    assert (outcome.plan is not None) is plan_known
    if stage == "result_projection":
        assert outcome.run_result is not None
        assert outcome.run_result.run_id == outcome.run_id
        assert outcome.run_result.status.value == "pass"
    else:
        assert outcome.run_result is None
    assert outcome.elapsed_ns >= 0
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [d.code for d in outcome.service_result.diagnostics] == [diagnostic_code]
    assert "private-preparation-error" not in repr(outcome)
    assert "super-secret" not in repr(outcome.service_result.to_dict())
    assert service.execute().to_dict() == outcome.service_result.to_dict()
    public = outcome.service_result.to_dict()
    assert set(public) == {"exit_category", "exit_code", "message", "diagnostics"}
    assert public["exit_code"] == 3
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 3
    assert diagnostic_code in cli.output
    diagnostic = outcome.service_result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message in cli.output
    assert diagnostic.hint in cli.output
    for token in ("private-preparation-error", "super-secret", outcome.run_id):
        assert token not in cli.output
        assert token not in caplog.text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-loaded-compiled-scope")
@pytest.mark.parametrize(
    "variant",
    [
        "missing_check",
        "extra_check",
        "duplicate_check",
        "wrong_check_id",
        "wrong_check_type",
        "wrong_check_contract",
        "reordered_checks",
        "missing_contract",
        "extra_contract",
        "reordered_contracts",
        "wrong_project",
        "wrong_run_id",
        "complete",
    ],
)
def test_invocation_rejects_results_outside_loaded_scope(tmp_path: Path, variant: str) -> None:
    write_project(tmp_path)
    write_compiled_checks(
        tmp_path,
        contract_name="alpha",
        checks=[
            _compiled_check_payload(check_id="first", name="first"),
            _compiled_check_payload(check_id="second", name="second"),
        ],
    )
    write_compiled_contract(tmp_path, contract_name="alpha")
    write_compiled_checks(tmp_path, contract_name="empty", checks=[])
    write_compiled_contract(tmp_path, contract_name="empty")

    first = CheckResult(
        check_id="first",
        name="first",
        check_type="row_count_diff",
        contract_name="alpha",
        status=CheckStatus.PASS,
        executed=True,
    )
    second = replace(first, check_id="second", name="second")
    checks = (first, second)
    if variant == "missing_check":
        checks = (first,)
    elif variant == "extra_check":
        checks += (replace(first, check_id="extra"),)
    elif variant == "duplicate_check":
        checks = (first, first)
    elif variant == "wrong_check_id":
        checks = (first, replace(second, check_id="foreign"))
    elif variant == "wrong_check_type":
        checks = (first, replace(second, check_type="sum_diff"))
    elif variant == "wrong_check_contract":
        checks = (first, replace(second, contract_name="foreign"))
    elif variant == "reordered_checks":
        checks = (second, first)

    alpha = ContractResult.from_check_results(contract_name="alpha", check_results=checks)
    empty = ContractResult.from_check_results(contract_name="empty", check_results=())
    contracts = (alpha, empty)
    if variant == "missing_contract":
        contracts = (alpha,)
    elif variant == "extra_contract":
        contracts += (replace(empty, contract_name="foreign"),)
    elif variant == "reordered_contracts":
        contracts = (empty, alpha)

    class ScopeEngine:
        def run(self, *args: Any, **kwargs: Any) -> RunResult:
            return RunResult.from_contract_results(
                run_id="foreign" if variant == "wrong_run_id" else kwargs["run_id"],
                project_name="foreign" if variant == "wrong_project" else kwargs["project_name"],
                started_at=kwargs["started_at"],
                finished_at="2026-11-27T10:00:00Z",
                contract_results=contracts,
            )

    outcome = RunService(start_path=tmp_path, engine=ScopeEngine())._execute_invocation()
    if variant == "complete":
        assert outcome.service_result.exit_category is ExitCategory.SUCCESS
        assert outcome.status.value == "completed"
    else:
        assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
        assert outcome.status.value == "failed"
        assert [d.code for d in outcome.service_result.diagnostics] == [
            "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"
        ]
    assert outcome.run_result is not None
    assert outcome.run_result.contract_results == contracts
    assert outcome.scope_facts.planned_contract_count == 2
    assert outcome.scope_facts.planned_check_count == 2
    assert outcome.scope_facts.finalized_check_count == len(checks)
    assert outcome.scope_facts.executed_check_count == len(checks)
    assert outcome.scope_facts.complete is (variant == "complete")
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
@pytest.mark.parametrize("timeout", [0, -1, True, False, 1.5, "private-timeout-canary"])
def test_invalid_invocation_timeout_stops_before_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: Any
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Invalid timeout must not start project preparation.")

    monkeypatch.setattr(run_service_module, "load_project_context", forbidden)
    result = RunService(start_path=tmp_path).execute(timeout_seconds=timeout)
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.diagnostics
    assert "private-timeout-canary" not in repr(result.to_dict())
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_preset_cancel_event_stops_before_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Preset cancellation must not start project preparation.")

    monkeypatch.setattr(run_service_module, "load_project_context", forbidden)
    event = Event()
    event.set()
    service = RunService(start_path=tmp_path)
    for _ in range(2):
        result = service.execute(cancel_event=event)
        assert result.exit_category is ExitCategory.RUNTIME_ERROR
        assert "RC_RUNTIME_RUN_CANCELLED" in {d.code for d in result.diagnostics}
        assert event.is_set()
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_large_explicit_timeout_preserves_existing_outcome(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    service = RunService(start_path=tmp_path)
    expected = service.execute().to_dict()
    event = Event()
    result = service.execute(timeout_seconds=10**100, cancel_event=event)
    assert result.to_dict() == expected
    assert not event.is_set()
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_cancellation_before_projection_seal_cannot_return_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    event = Event()

    def passing_dispatch(self: CheckDispatcher, check: Any) -> CheckResult:
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=CheckStatus.PASS,
            executed=True,
        )

    original = run_service_module._run_service_result

    def project_then_cancel(result: RunResult) -> Any:
        projected = original(result)
        assert projected.exit_category is ExitCategory.SUCCESS
        event.set()
        return projected

    monkeypatch.setattr(CheckDispatcher, "dispatch", passing_dispatch)
    monkeypatch.setattr(run_service_module, "_run_service_result", project_then_cancel)
    outcome = RunService(start_path=tmp_path)._execute_invocation(cancel_event=event)
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert outcome.status.value == "failed"
    assert "RC_RUNTIME_RUN_CANCELLED" in {d.code for d in outcome.service_result.diagnostics}
    assert outcome.run_result is not None
    assert outcome.run_result.status.value == "pass"
    assert outcome.scope_facts.executed_check_count == 1
    assert event.is_set()
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_cancelled_run_never_dispatches_later_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_project(tmp_path)
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(check_id="first", name="first"),
            _compiled_check_payload(check_id="second", name="second"),
        ],
    )
    write_compiled_contract(tmp_path)
    event = Event()
    dispatched: list[str] = []

    def dispatch_then_cancel(self: CheckDispatcher, check: Any) -> CheckResult:
        dispatched.append(check.id)
        event.set()
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=CheckStatus.PASS,
            executed=True,
        )

    monkeypatch.setattr(CheckDispatcher, "dispatch", dispatch_then_cancel)
    outcome = RunService(start_path=tmp_path)._execute_invocation(cancel_event=event)
    assert dispatched == ["first"]
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert outcome.run_result is not None
    checks = outcome.run_result.contract_results[0].check_results
    assert len(checks) == 2
    assert checks[1].check_id == "second"
    assert checks[1].status is CheckStatus.NOT_EXECUTABLE
    assert checks[1].reason_code is not None
    assert checks[1].reason_code.value == "run_cancelled"
    assert not checks[1].executed
    assert outcome.scope_facts.complete is True
    assert outcome.scope_facts.finalized_check_count == 2
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
@pytest.mark.parametrize("first", ["deadline", "cancelled", "sealed"])
def test_run_control_latches_observation_and_seal(first: str) -> None:
    event = Event()
    now = 0
    control = _RunControl(started_ns=0, timeout_seconds=1, cancel_event=event, clock=lambda: now)
    assert control.observe() is None
    if first == "sealed":
        assert control.seal() is None
        event.set()
        now = 2_000_000_000
        assert control.observe() is None
        return
    now = 1_000_000_000
    if first == "cancelled":
        event.set()
        expected = _StopCause.CANCELLED
    else:
        expected = _StopCause.DEADLINE
    assert control.observe() is expected
    event.set()
    assert control.seal() is expected
    assert control.observe() is expected


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_deadline_consumed_in_preparation_prevents_artifact_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_project(tmp_path)
    now = 0
    original = run_service_module.load_project_context

    def prepare(*args: Any, **kwargs: Any) -> Any:
        nonlocal now
        result = original(*args, **kwargs)
        now = 1_000_000_000
        return result

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Expired invocation must not load artifacts.")

    monkeypatch.setattr(run_service_module, "monotonic_ns", lambda: now)
    monkeypatch.setattr(run_service_module, "load_project_context", prepare)
    monkeypatch.setattr(CompiledCheckLoader, "load", forbidden)
    outcome = RunService(start_path=tmp_path)._execute_invocation(timeout_seconds=1)
    assert outcome.stop_cause is _StopCause.DEADLINE
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert outcome.elapsed_ns == 1_000_000_000
    assert outcome.plan is None and outcome.run_result is None
    assert "RC_RUNTIME_RUN_DEADLINE_EXCEEDED" in {
        d.code for d in outcome.service_result.diagnostics
    }
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_native_control_joins_borrowed_interrupt_before_return() -> None:
    event = Event()
    control = _RunControl(started_ns=0, timeout_seconds=None, cancel_event=event, clock=lambda: 0)
    entered = Event()
    call_returning = Event()
    interrupt_entered = Event()
    release_interrupt = Event()
    returned = Event()
    outcomes: list[_StopCause] = []

    def native() -> int:
        entered.set()
        if not interrupt_entered.wait(5):
            raise RuntimeError("No interrupt request.")
        call_returning.set()
        return 1

    def interrupt() -> bool:
        interrupt_entered.set()
        return release_interrupt.wait(5)

    def run() -> None:
        try:
            control.native_call(native, interrupt)
        except _RunStoppedError as exc:
            outcomes.append(exc.cause)
        finally:
            returned.set()

    worker = Thread(target=run)
    worker.start()
    try:
        assert entered.wait(5)
        event.set()
        assert interrupt_entered.wait(5)
        assert call_returning.wait(5)
        assert not returned.wait(0.05)
    finally:
        release_interrupt.set()
        worker.join(5)
        control.close_observer()
    assert not worker.is_alive()
    assert returned.is_set()
    assert outcomes == [_StopCause.CANCELLED]
    assert control.seal() is _StopCause.CANCELLED


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_native_control_repeats_failed_interrupt_without_retrying_call() -> None:
    event = Event()
    control = _RunControl(started_ns=0, timeout_seconds=None, cancel_event=event, clock=lambda: 0)
    calls: list[int] = []
    interrupts: list[int] = []
    interrupted = Event()

    def native() -> int:
        calls.append(1)
        event.set()
        if not interrupted.wait(5):
            raise RuntimeError("No repeated interrupt request.")
        return 1

    def interrupt() -> bool:
        interrupts.append(1)
        if len(interrupts) == 1:
            raise RuntimeError("Synthetic interrupt failure.")
        interrupted.set()
        return True

    try:
        with pytest.raises(_RunStoppedError) as stopped:
            control.native_call(native, interrupt)
        assert stopped.value.cause is _StopCause.CANCELLED
        with pytest.raises(_RunStoppedError):
            control.native_call(native, interrupt)
        assert calls == [1]
        assert len(interrupts) >= 2
    finally:
        control.close_observer()
    assert control.seal() is _StopCause.CANCELLED


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_embedded_base_exception_joins_control_observer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recon_core.services._run_lifecycle import _RunInvocation

    started: list[Thread] = []
    controls: list[_RunControl] = []

    def evaluate(self: RunService, invocation: _RunInvocation) -> Any:
        control = invocation.control
        assert control is not None
        assert control.native_call(lambda: 42, lambda: False) == 42
        assert control._observer is not None
        started.append(control._observer)
        controls.append(control)
        raise KeyboardInterrupt

    monkeypatch.setattr(RunService, "_evaluate_invocation", evaluate)
    try:
        with pytest.raises(KeyboardInterrupt):
            RunService(start_path=tmp_path).execute(cancel_event=Event())
        assert len(started) == 1
        assert not started[0].is_alive()
    finally:
        for control in controls:
            control.close_observer()
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
@pytest.mark.parametrize("status", [CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.ERROR])
def test_stop_after_prerequisite_preserves_result_and_finalizes_dependents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: CheckStatus
) -> None:
    write_project(tmp_path)
    dependent = _compiled_check_payload(check_id="dependent", name="dependent")
    dependent["prerequisites"] = ["prerequisite"]
    write_compiled_checks(
        tmp_path,
        checks=[
            dependent,
            _compiled_check_payload(check_id="prerequisite", name="prerequisite"),
            _compiled_check_payload(check_id="later", name="later"),
        ],
    )
    write_compiled_contract(tmp_path)
    event = Event()
    dispatched: list[str] = []
    diagnostic = Diagnostic(
        code="RC_TEST_PRIOR_FAILURE",
        severity=DiagnosticSeverity.ERROR,
        message="Prior check failed independently.",
    )

    def dispatch(self: CheckDispatcher, check: Any) -> CheckResult:
        dispatched.append(check.id)
        event.set()
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=status,
            executed=status is not CheckStatus.ERROR,
            message=diagnostic.message if status is CheckStatus.ERROR else None,
            diagnostics=(diagnostic,) if status is CheckStatus.ERROR else (),
        )

    monkeypatch.setattr(CheckDispatcher, "dispatch", dispatch)
    outcome = RunService(start_path=tmp_path)._execute_invocation(cancel_event=event)
    assert dispatched == ["prerequisite"]
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert outcome.scope_facts.complete is True
    assert outcome.run_result is not None
    dependent_result, prior, later = outcome.run_result.contract_results[0].check_results
    assert prior.status is status
    if status is CheckStatus.ERROR:
        assert diagnostic in prior.diagnostics
        assert diagnostic in outcome.service_result.diagnostics
    for result in (dependent_result, later):
        assert result.status is CheckStatus.NOT_EXECUTABLE
        assert result.reason_code is CheckReason.RUN_CANCELLED
        assert result.blocked_by == ()
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_explicit_control_rejects_unproven_injected_engine(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    service = RunService(start_path=tmp_path, engine=_RaisingEngine())
    result = service.execute(cancel_event=Event())
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [d.code for d in result.diagnostics] == ["RC_RUNTIME_RUN_CONTROL_UNAVAILABLE"]
    _assert_no_runtime_outputs(tmp_path)
