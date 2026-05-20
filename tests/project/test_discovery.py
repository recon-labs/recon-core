from pathlib import Path

from recon_core.project import find_project_root


def test_find_project_root_returns_current_directory_when_marker_exists(tmp_path: Path) -> None:
    (tmp_path / "recon_project.yml").write_text("name: ecommerce_recon\n", encoding="utf-8")

    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_searches_parent_directories(tmp_path: Path) -> None:
    (tmp_path / "recon_project.yml").write_text("name: ecommerce_recon\n", encoding="utf-8")
    nested_dir = tmp_path / "contracts" / "nested"
    nested_dir.mkdir(parents=True)

    assert find_project_root(nested_dir) == tmp_path


def test_find_project_root_accepts_file_start_path(tmp_path: Path) -> None:
    (tmp_path / "recon_project.yml").write_text("name: ecommerce_recon\n", encoding="utf-8")
    contract_file = tmp_path / "contracts" / "customer_revenue.yml"
    contract_file.parent.mkdir()
    contract_file.write_text("name: customer_revenue\n", encoding="utf-8")

    assert find_project_root(contract_file) == tmp_path


def test_find_project_root_returns_none_when_marker_is_missing(tmp_path: Path) -> None:
    nested_dir = tmp_path / "contracts"
    nested_dir.mkdir()

    assert find_project_root(nested_dir) is None
