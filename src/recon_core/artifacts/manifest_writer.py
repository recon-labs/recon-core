"""Manifest artifact writer."""

import json
from pathlib import Path

from recon_core.parser import Manifest

MANIFEST_FILE_NAME = "manifest.json"


class ManifestWriter:
    """Write manifest artifacts to a target directory."""

    def write(self, manifest: Manifest, target_path: Path) -> Path:
        target_path.mkdir(parents=True, exist_ok=True)
        output_path = target_path / MANIFEST_FILE_NAME
        output_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path
