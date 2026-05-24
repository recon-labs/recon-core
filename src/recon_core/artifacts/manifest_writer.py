"""Manifest artifact writer."""

import json
from pathlib import Path

from recon_core.artifacts._paths import ensure_real_artifact_directory, ensure_safe_artifact_write
from recon_core.parser import Manifest

MANIFEST_FILE_NAME = "manifest.json"


class ManifestWriter:
    """Write manifest artifacts to a target directory."""

    def write(self, manifest: Manifest, target_path: Path) -> Path:
        ensure_real_artifact_directory(target_path)
        output_path = target_path / MANIFEST_FILE_NAME
        ensure_safe_artifact_write(output_path, overwrite=True)
        output_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path
