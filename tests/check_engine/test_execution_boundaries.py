"""Check-engine execution boundary tests."""

import ast
from pathlib import Path

from recon_core.check_engine import execution_support as execution_support_module
from recon_core.check_engine import key_safety as key_safety_module


def test_key_safety_does_not_import_row_count_execution_module() -> None:
    imported_modules = _imported_modules(Path(key_safety_module.__file__))

    assert "recon_core.check_engine.execution" not in imported_modules


def test_execution_support_does_not_import_duckdb_adapter_module() -> None:
    imported_modules = _imported_modules(Path(execution_support_module.__file__))

    assert "recon_core.adapters.duckdb" not in imported_modules
    assert "recon_core.adapters.duckdb.adapter" not in imported_modules


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
