"""Check-engine execution boundary tests."""

import ast
from pathlib import Path

from recon_core.check_engine import engine as engine_module
from recon_core.check_engine import execution_support as execution_support_module
from recon_core.check_engine import key_safety as key_safety_module
from recon_core.check_engine import prerequisites as prerequisites_module
from recon_core.check_engine import result_metadata as result_metadata_module
from recon_core.check_engine import runtime as runtime_module
from recon_core.check_engine import scan_budget as scan_budget_module
from recon_core.services import run as run_service_module


def test_key_safety_does_not_import_row_count_execution_module() -> None:
    imported_modules = _imported_modules(Path(key_safety_module.__file__))

    assert "recon_core.check_engine.execution" not in imported_modules


def test_execution_support_does_not_import_duckdb_adapter_module() -> None:
    imported_modules = _imported_modules(Path(execution_support_module.__file__))

    assert "recon_core.artifacts" not in imported_modules
    assert "recon_core.adapters" not in imported_modules
    assert "recon_core.adapters.duckdb" not in imported_modules
    assert "recon_core.adapters.duckdb.adapter" not in imported_modules


def test_check_engine_and_run_service_do_not_import_duckdb_runtime_modules() -> None:
    module_paths = (
        Path(engine_module.__file__),
        Path(execution_support_module.__file__),
        Path(key_safety_module.__file__),
        Path(prerequisites_module.__file__),
        Path(result_metadata_module.__file__),
        Path(runtime_module.__file__),
        Path(scan_budget_module.__file__),
        Path(run_service_module.__file__),
    )

    for module_path in module_paths:
        imported_modules = _imported_modules(module_path)
        imported_names = _imported_names(module_path)

        assert "DuckDbSqlRenderer" not in imported_names
        assert not any(
            imported_module == "recon_core.adapters.duckdb"
            or imported_module.startswith("recon_core.adapters.duckdb.")
            for imported_module in imported_modules
        )


def test_prerequisite_helper_keeps_runtime_dependencies_out() -> None:
    imported_modules = _imported_modules(Path(prerequisites_module.__file__))

    assert "recon_core.check_engine.execution_support" not in imported_modules
    assert "recon_core.check_engine.scan_budget" not in imported_modules
    assert "recon_core.services.run" not in imported_modules
    assert "recon_core.adapters" not in imported_modules
    assert not any(
        imported_module.startswith("recon_core.adapters.")
        for imported_module in imported_modules
    )


def test_runtime_router_does_not_prepare_runtime_dependencies() -> None:
    imported_modules = _imported_modules(Path(runtime_module.__file__))

    assert "recon_core.services.run" not in imported_modules
    assert "recon_core.adapters.runtime_setup" not in imported_modules
    assert "recon_core.adapters.runtime_safety" not in imported_modules


def test_result_metadata_helper_keeps_runtime_dependencies_out() -> None:
    imported_modules = _imported_modules(Path(result_metadata_module.__file__))

    assert "recon_core.check_engine.execution_support" not in imported_modules
    assert "recon_core.check_engine.scan_budget" not in imported_modules
    assert "recon_core.services.run" not in imported_modules
    assert "recon_core.adapters" not in imported_modules
    assert not any(
        imported_module.startswith("recon_core.adapters.")
        for imported_module in imported_modules
    )


def test_scan_budget_policy_stays_isolated_from_runtime_dependencies() -> None:
    imported_modules = _imported_modules(Path(scan_budget_module.__file__))

    assert "recon_core.artifacts" not in imported_modules
    assert "recon_core.compiler" not in imported_modules
    assert "recon_core.services.run" not in imported_modules
    assert "recon_core.adapters" not in imported_modules
    assert not any(
        imported_module.startswith("recon_core.adapters.")
        for imported_module in imported_modules
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.rpartition(".")[2] for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return names
