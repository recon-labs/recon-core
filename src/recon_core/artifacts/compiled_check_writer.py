"""Compiled checks artifact writer."""

from pathlib import Path

from recon_core.artifacts._paths import (
    artifact_output_path,
    ensure_real_artifact_directory,
    ensure_safe_artifact_write,
)
from recon_core.artifacts._yaml import dump_artifact_yaml
from recon_core.compiler.models import CompiledChecksArtifact

COMPILED_CHECKS_DIR_NAME = "compiled_checks"


class CompiledCheckWriter:
    """Write compiled checks artifacts to a target directory."""

    def write(
        self,
        artifact: CompiledChecksArtifact,
        target_path: Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        output_dir = target_path / COMPILED_CHECKS_DIR_NAME
        ensure_real_artifact_directory(output_dir)
        output_path = artifact_output_path(output_dir, artifact.contract.name)
        ensure_safe_artifact_write(output_path, overwrite=overwrite)
        output_path.write_text(
            dump_artifact_yaml(artifact.to_dict()),
            encoding="utf-8",
        )
        return output_path
