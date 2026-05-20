"""Manifest artifact models and builder."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypedDict

from recon_core._version import get_version
from recon_core.diagnostics import Diagnostic, DiagnosticDict, DiagnosticSeverity
from recon_core.parser.contracts import AuthoredContract, AuthoredContractSummaryDict
from recon_core.parser.files import ResourceFile, ResourceFileDict

MANIFEST_ARTIFACT_TYPE = "manifest"
MANIFEST_ARTIFACT_VERSION = 1
DUPLICATE_CONTRACT = "RC_PARSE_DUPLICATE_CONTRACT"


class ManifestProjectDict(TypedDict):
    name: str
    config_version: int
    version: str | None


class ManifestDict(TypedDict):
    artifact_type: str
    artifact_version: int
    recon_version: str
    generated_at: str
    project: ManifestProjectDict
    files: dict[str, ResourceFileDict]
    contracts: dict[str, AuthoredContractSummaryDict]
    diagnostics: list[DiagnosticDict]


@dataclass(frozen=True, slots=True)
class ManifestProject:
    """Project metadata included in manifest artifacts."""

    name: str
    config_version: int
    version: str | None = None

    def to_dict(self) -> ManifestProjectDict:
        return {
            "name": self.name,
            "config_version": self.config_version,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class Manifest:
    """Parsed project manifest artifact."""

    project: ManifestProject
    files: dict[str, ResourceFile]
    contracts: dict[str, AuthoredContract]
    diagnostics: tuple[Diagnostic, ...]
    recon_version: str
    generated_at: str
    artifact_type: str = MANIFEST_ARTIFACT_TYPE
    artifact_version: int = MANIFEST_ARTIFACT_VERSION

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )

    def to_dict(self) -> ManifestDict:
        return {
            "artifact_type": self.artifact_type,
            "artifact_version": self.artifact_version,
            "recon_version": self.recon_version,
            "generated_at": self.generated_at,
            "project": self.project.to_dict(),
            "files": {
                path: resource_file.to_dict() for path, resource_file in sorted(self.files.items())
            },
            "contracts": {
                name: contract.to_summary_dict()
                for name, contract in sorted(self.contracts.items())
            },
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


def build_manifest(
    *,
    project: ManifestProject,
    files: tuple[ResourceFile, ...],
    contracts: tuple[AuthoredContract, ...],
    diagnostics: tuple[Diagnostic, ...] = (),
    recon_version: str | None = None,
    generated_at: str | None = None,
) -> Manifest:
    """Build a manifest from parsed project resources."""
    manifest_contracts: dict[str, AuthoredContract] = {}
    manifest_diagnostics = list(diagnostics)

    for contract in contracts:
        existing_contract = manifest_contracts.get(contract.name)
        if existing_contract is not None:
            manifest_diagnostics.append(_duplicate_contract_diagnostic(contract, existing_contract))
            continue
        manifest_contracts[contract.name] = contract

    return Manifest(
        project=project,
        files={resource_file.relative_path: resource_file for resource_file in files},
        contracts=manifest_contracts,
        diagnostics=tuple(manifest_diagnostics),
        recon_version=get_version() if recon_version is None else recon_version,
        generated_at=_current_timestamp() if generated_at is None else generated_at,
    )


def _duplicate_contract_diagnostic(
    duplicate_contract: AuthoredContract,
    existing_contract: AuthoredContract,
) -> Diagnostic:
    return Diagnostic(
        code=DUPLICATE_CONTRACT,
        severity=DiagnosticSeverity.ERROR,
        message=f"Contract name {duplicate_contract.name} is defined more than once.",
        resource_type="contract",
        resource_name=duplicate_contract.name,
        path=duplicate_contract.source_location.path,
        hint=f"First definition was found at {existing_contract.source_location.path}.",
    )


def _current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
