import json
from pathlib import Path

from recon_core.artifacts import ManifestWriter
from recon_core.parser import (
    AuthoredContract,
    AuthoredEndpoint,
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
