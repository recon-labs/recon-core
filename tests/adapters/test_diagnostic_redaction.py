"""Adapter diagnostic redaction helper tests."""

import ast
import importlib
from collections.abc import Iterable
from pathlib import Path

from recon_core.adapters._diagnostic_redaction_core import sanitize_adapter_diagnostic
from recon_core.adapters._diagnostic_redaction_matching import (
    text_mentions_config_token,
    text_mentions_numeric_config_token,
)
from recon_core.adapters._diagnostic_redaction_tokens import adapter_diagnostic_config_tokens
from recon_core.adapters.diagnostic_redaction import ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def test_redaction_core_suppresses_unsafe_codes_and_replacement_fields() -> None:
    token_context = adapter_diagnostic_config_tokens(
        {
            "database": "duckdb://admin:super-secret@warehouse.local:12/app?token=abc123",
            "password": "super-secret",
            "port": 12,
        },
        adapter_type="duckdb",
    )
    diagnostic = Diagnostic(
        code="RC12LEAK",
        severity=DiagnosticSeverity.ERROR,
        message="Adapter failed against warehouse.local.",
        resource_type="adapter",
        resource_name="endpoint-12.0",
        path="adapter://abc123",
        line=12,
        column=12,
        hint="Inspect super-secret locally.",
    )

    sanitized = sanitize_adapter_diagnostic(
        diagnostic,
        connection_type="duckdb",
        connection_name="warehouse",
        config_tokens=token_context.config_tokens,
        code_config_tokens=token_context.code_config_tokens,
        numeric_field_tokens=token_context.numeric_field_tokens,
        suppressed_code=ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED,
        suppression_reason="profile diagnostics must not expose rendered connection config.",
    )

    public_text = "\n".join(
        str(value)
        for value in (
            sanitized.code,
            sanitized.message,
            sanitized.resource_type,
            sanitized.resource_name,
            sanitized.path,
            sanitized.line,
            sanitized.column,
            sanitized.hint,
        )
        if value is not None
    )

    assert sanitized.code == "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED"
    assert sanitized.severity is DiagnosticSeverity.ERROR
    assert sanitized.resource_type == "adapter"
    assert sanitized.resource_name == "duckdb"
    assert sanitized.path is None
    assert sanitized.line is None
    assert sanitized.column is None
    assert "adapter diagnostic text was suppressed" in sanitized.message
    assert "super-secret" not in public_text
    assert "warehouse.local" not in public_text
    assert "abc123" not in public_text
    assert "\n12\n" not in f"\n{public_text}\n"


def test_redaction_core_preserves_safe_code_when_message_is_unsafe() -> None:
    token_context = adapter_diagnostic_config_tokens(
        {"password": "super-secret"},
        adapter_type="duckdb",
    )
    diagnostic = Diagnostic(
        code="RC_ADAPTER_CAPABILITY_UNSUPPORTED",
        severity=DiagnosticSeverity.ERROR,
        message="Adapter failed with password=super-secret.",
    )

    sanitized = sanitize_adapter_diagnostic(
        diagnostic,
        connection_type="duckdb",
        connection_name="warehouse",
        config_tokens=token_context.config_tokens,
        code_config_tokens=token_context.code_config_tokens,
        numeric_field_tokens=token_context.numeric_field_tokens,
        suppressed_code=ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED,
        suppression_reason="profile diagnostics must not expose rendered connection config.",
    )

    assert sanitized.code == "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    assert "super-secret" not in sanitized.message


def test_redaction_core_exposes_matching_helpers_for_compile_metadata() -> None:
    token_context = adapter_diagnostic_config_tokens(
        {
            "host": "warehouse.local",
            "port": "12.0",
        },
        adapter_type="duckdb",
    )

    assert text_mentions_config_token("using WAREHOUSE.LOCAL", token_context.config_tokens)
    assert text_mentions_numeric_config_token("using port +12", token_context.numeric_field_tokens)
    assert not text_mentions_config_token("using duckdb", token_context.config_tokens)


def test_adapter_redaction_helpers_do_not_import_service_artifact_or_renderer_modules() -> None:
    forbidden_modules = (
        "duckdb",
        "recon_core.adapters.duckdb",
        "recon_core.adapters.rendering",
        "recon_core.artifacts",
        "recon_core.services",
    )

    for module_name in (
        "recon_core.adapters._diagnostic_redaction_core",
        "recon_core.adapters._diagnostic_redaction_matching",
        "recon_core.adapters._diagnostic_redaction_tokens",
        "recon_core.adapters.diagnostic_redaction",
    ):
        assert not _imports_matching(module_name, forbidden_modules), module_name


def test_runtime_redaction_callers_do_not_import_compile_privacy_helpers() -> None:
    forbidden = "recon_core.services._compile_diagnostic_privacy"
    for relative_path in (
        "src/recon_core/adapters/runtime_setup.py",
        "src/recon_core/adapters/registry.py",
        "src/recon_core/services/run.py",
        "src/recon_core/check_engine/execution_support.py",
    ):
        assert forbidden not in _repo_path(relative_path).read_text(encoding="utf-8")


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


def _repo_path(relative_path: str) -> Path:
    return Path(__file__).resolve().parents[2] / relative_path


def _imported_modules(tree: ast.AST) -> set[str]:
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules
