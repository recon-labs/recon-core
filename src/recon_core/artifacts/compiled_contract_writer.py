"""Compiled contract artifact writer."""

from pathlib import Path

from recon_core.artifacts._yaml import dump_artifact_yaml
from recon_core.compiler.models import CompiledContractArtifact

COMPILED_CONTRACTS_DIR_NAME = "compiled_contracts"


class CompiledContractWriter:
    """Write compiled contract artifacts to a target directory."""

    def write(self, artifact: CompiledContractArtifact, target_path: Path) -> Path:
        output_dir = target_path / COMPILED_CONTRACTS_DIR_NAME
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{artifact.contract.name}.yml"
        output_path.write_text(
            dump_artifact_yaml(artifact.to_dict()),
            encoding="utf-8",
        )
        return output_path
