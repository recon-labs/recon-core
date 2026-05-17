from pathlib import Path

import pytest
import yaml

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
    config = yaml.safe_load(content)

    assert config["name"] == "ecommerce_recon"
    assert config["config-version"] == 1
    assert config["contract-paths"] == ["contracts"]
    assert config["target-path"] == "target"
    assert config["report-path"] == "reports"
    assert config["state-path"] == "state"


@pytest.mark.parametrize("project_name", ["yes", "null", "123", "#foo", "name: value"])
def test_init_service_writes_project_name_as_yaml_string(tmp_path: Path, project_name: str) -> None:
    InitService(project_name=project_name, base_dir=tmp_path).execute()

    content = (tmp_path / project_name / "recon_project.yml").read_text()
    config = yaml.safe_load(content)

    assert config["name"] == project_name


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


@pytest.mark.parametrize("project_name", ["../outside", "nested/project", r"nested\project"])
def test_init_service_rejects_project_names_that_are_paths(
    tmp_path: Path, project_name: str
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    result = InitService(project_name=project_name, base_dir=base_dir).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == f"Invalid project name: {project_name}"
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "RC_CONFIG_INIT_INVALID_PROJECT_NAME"
    assert not (base_dir / project_name).exists()
    assert not (tmp_path / "outside").exists()


def test_init_service_rejects_absolute_project_path(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    project_name = str(tmp_path / "outside_absolute")

    result = InitService(project_name=project_name, base_dir=base_dir).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == f"Invalid project name: {project_name}"
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "RC_CONFIG_INIT_INVALID_PROJECT_NAME"
    assert not (tmp_path / "outside_absolute").exists()
