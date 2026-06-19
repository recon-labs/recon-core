"""Profile connection-reference boundary tests."""

import ast
from dataclasses import dataclass
from pathlib import Path

from recon_core.profiles import loader as profile_loader_module
from recon_core.profiles.connection_references import (
    referenced_connection_names,
    referenced_connection_names_from_compiled_contracts,
)


@dataclass(frozen=True, slots=True)
class _EndpointReference:
    connection: str


@dataclass(frozen=True, slots=True)
class _ContractReference:
    source: _EndpointReference
    target: _EndpointReference


def test_referenced_connection_names_uses_structural_contract_references() -> None:
    names = referenced_connection_names(
        (
            _ContractReference(
                source=_EndpointReference(connection="legacy"),
                target=_EndpointReference(connection="warehouse"),
            ),
            _ContractReference(
                source=_EndpointReference(connection="legacy"),
                target=_EndpointReference(connection="analytics"),
            ),
        )
    )

    assert names == ("analytics", "legacy", "warehouse")


def test_compiled_reference_wrapper_uses_structural_contract_references() -> None:
    names = referenced_connection_names_from_compiled_contracts(
        (
            _ContractReference(
                source=_EndpointReference(connection="warehouse"),
                target=_EndpointReference(connection="warehouse"),
            ),
        )
    )

    assert names == ("warehouse",)


def test_profile_loader_does_not_import_contract_shape_modules() -> None:
    loader_path = Path(profile_loader_module.__file__)
    tree = ast.parse(loader_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert "recon_core.parser.contracts" not in imported_modules
    assert "recon_core.artifacts.compiled_contract_loader" not in imported_modules
