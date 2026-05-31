import json
from pathlib import Path

import pytest

from recon_core.artifacts import ManifestWriter
from recon_core.parser import (
    AuthoredContract,
    AuthoredEndpoint,
    Manifest,
    ManifestProject,
    build_manifest,
)
from recon_core.parser.models import SourceLocation


def test_manifest_writer_creates_target_directory_and_writes_json(tmp_path: Path) -> None:
    manifest = build_manifest(
        project=ManifestProject(name="ecommerce_recon", config_version=1),
        files=(),
        contracts=(
            AuthoredContract(
                name="customer_revenue",
                version=1,
                source=AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
                target=AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
                checks={"use": ["recon_core.basic_equivalence"]},
                source_location=SourceLocation(path="contracts/customer.yml"),
            ),
        ),
        recon_version="0.0.test",
        generated_at="2026-05-20T12:00:00Z",
    )

    output_path = ManifestWriter().write(manifest, tmp_path / "target" / "nested")

    assert output_path == tmp_path / "target" / "nested" / "manifest.json"
    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest.to_dict()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_manifest_writer_overwrites_existing_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    writer = ManifestWriter()
    output_path = writer.write(manifest, tmp_path / "target")
    output_path.write_text("{}\n", encoding="utf-8")

    writer.write(manifest, tmp_path / "target")

    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest.to_dict()


def test_manifest_writer_rejects_symlinked_target_directory(tmp_path: Path) -> None:
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    try:
        target_path.symlink_to(external_path, target_is_directory=True)
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        ManifestWriter().write(_manifest(), target_path)

    assert not (external_path / "manifest.json").exists()


def test_manifest_writer_rejects_exact_manifest_symlink(tmp_path: Path) -> None:
    target_path = tmp_path / "target"
    external_path = tmp_path / "external_manifest.json"
    target_path.mkdir()
    external_path.write_text("external\n", encoding="utf-8")
    try:
        (target_path / "manifest.json").symlink_to(external_path)
    except OSError:
        pytest.skip("Filesystem does not support file symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        ManifestWriter().write(_manifest(), target_path)

    assert external_path.read_text(encoding="utf-8") == "external\n"


def _manifest() -> Manifest:
    return build_manifest(
        project=ManifestProject(name="ecommerce_recon", config_version=1),
        files=(),
        contracts=(
            AuthoredContract(
                name="customer_revenue",
                version=1,
                source=AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
                target=AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
                checks={"use": ["recon_core.basic_equivalence"]},
                source_location=SourceLocation(path="contracts/customer.yml"),
            ),
        ),
        recon_version="0.0.test",
        generated_at="2026-05-20T12:00:00Z",
    )
