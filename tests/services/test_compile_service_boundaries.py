from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_compile_service_orchestrator_avoids_concrete_duckdb_renderer_imports() -> None:
    text = _read_text("src/recon_core/services/compile.py")

    assert "DuckDbSqlRenderer" not in text
    assert "recon_core.adapters.duckdb" not in text


def test_compile_artifact_helper_avoids_profile_adapter_and_renderer_setup() -> None:
    text = _read_text("src/recon_core/services/_compile_artifacts.py")

    forbidden = (
        "load_selected_profile",
        "AdapterRegistry",
        "default_adapter_registry",
        "DuckDbSqlRenderer",
        "recon_core.adapters.duckdb",
        "render_check_sql",
        "connection_config_tokens",
        "sanitize_profile_backed",
    )
    for token in forbidden:
        assert token not in text


def test_compile_adapter_setup_helper_avoids_artifact_publication() -> None:
    text = _read_text("src/recon_core/services/_compile_adapter_setup.py")

    forbidden = (
        "CompiledCheckWriter",
        "CompiledContractWriter",
        "CompiledSqlWriter",
        "clear_compiled",
        "discard_compiled",
        "shutil",
        "ensure_real_artifact_directory",
        "reject_symlinked",
        "COMPILED_SQL_DIR_NAME",
        "COMPILED_CHECKS_DIR_NAME",
        "COMPILED_CONTRACTS_DIR_NAME",
    )
    for token in forbidden:
        assert token not in text


def test_compiler_modules_do_not_import_compile_profile_redaction_helpers() -> None:
    compiler_root = ROOT / "src" / "recon_core" / "compiler"

    forbidden = (
        "recon_core.services._compile_diagnostic_privacy",
        "connection_config_tokens",
        "sanitize_profile_backed",
    )
    for path in compiler_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
