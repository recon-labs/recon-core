"""Profile loader decomposition boundary tests."""

import ast
import importlib
from collections.abc import Iterable
from pathlib import Path

PROFILE_PRIVATE_HELPERS = (
    "recon_core.profiles._diagnostics",
    "recon_core.profiles._profile_yaml",
    "recon_core.profiles._rendering",
    "recon_core.profiles._selection",
)


def test_profile_private_helpers_do_not_import_adapter_or_service_modules() -> None:
    forbidden_prefixes = (
        "duckdb",
        "recon_core.adapters",
        "recon_core.services",
    )

    for module_name in PROFILE_PRIVATE_HELPERS:
        assert not _imports_matching(module_name, forbidden_prefixes), module_name


def test_profile_private_helpers_do_not_import_contract_shape_modules() -> None:
    forbidden_modules = (
        "recon_core.artifacts",
        "recon_core.parser.contracts",
    )

    for module_name in ("recon_core.profiles.loader", *PROFILE_PRIVATE_HELPERS):
        assert not _imports_matching(module_name, forbidden_modules), module_name


def test_profile_rendering_helper_does_not_use_broad_template_execution() -> None:
    module_path = _module_path("recon_core.profiles._rendering")
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = _imported_modules(tree)
    assert not any(module.startswith("jinja") for module in imported_modules)

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "eval" not in called_names
    assert "exec" not in called_names
    assert "__import__" not in called_names


def _imports_matching(module_name: str, forbidden_modules: Iterable[str]) -> tuple[str, ...]:
    tree = ast.parse(_module_path(module_name).read_text(encoding="utf-8"))
    imported_modules = _imported_modules(tree)
    forbidden = tuple(forbidden_modules)
    return tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == forbidden_module
            or imported_module.startswith(f"{forbidden_module}.")
            for forbidden_module in forbidden
        )
    )


def _module_path(module_name: str) -> Path:
    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    return Path(module.__file__)


def _imported_modules(tree: ast.AST) -> set[str]:
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules
