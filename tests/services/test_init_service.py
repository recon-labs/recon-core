from pathlib import Path

from recon_core.services import InitService
from recon_core.services.results import ExitCategory


def test_init_service_creates_safe_starter_project(tmp_path: Path) -> None:
    result = InitService(project_name="ecommerce_recon", base_dir=tmp_path).execute()

    project_dir = tmp_path / "ecommerce_recon"

    assert result.succeeded
    assert result.message == f"Created Recon project at {project_dir}"
    assert (project_dir / "recon_project.yml").is_file()
    assert (project_dir / ".gitignore").is_file()
    assert (project_dir / "connections" / "profiles.yml.example").is_file()

    for directory in (
        "contracts",
        "sample_policies",
        "tolerances",
        "schema_policies",
        "target",
        "reports",
        "state",
    ):
        assert (project_dir / directory).is_dir()


def test_init_service_writes_project_config(tmp_path: Path) -> None:
    InitService(project_name="ecommerce_recon", base_dir=tmp_path).execute()

    content = (tmp_path / "ecommerce_recon" / "recon_project.yml").read_text()

    assert "name: ecommerce_recon\n" in content
    assert "config-version: 1\n" in content
    assert "contract-paths:\n  - contracts\n" in content
    assert "target-path: target\n" in content
    assert "report-path: reports\n" in content
    assert "state-path: state\n" in content


def test_init_service_writes_secret_safe_profiles_example(tmp_path: Path) -> None:
    InitService(project_name="ecommerce_recon", base_dir=tmp_path).execute()

    content = (tmp_path / "ecommerce_recon" / "connections" / "profiles.yml.example").read_text()

    assert "password: \"{{ env_var('RECON_EXAMPLE_PASSWORD') }}\"" in content
    assert "change_me" not in content


def test_init_service_does_not_overwrite_existing_path(tmp_path: Path) -> None:
    project_dir = tmp_path / "ecommerce_recon"
    project_dir.mkdir()

    result = InitService(project_name="ecommerce_recon", base_dir=tmp_path).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == f"Path already exists: {project_dir}"
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "RC_CONFIG_INIT_PATH_EXISTS"
